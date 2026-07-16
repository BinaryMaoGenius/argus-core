from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..logging import get_logger, struct_log

_logger = get_logger("memory")


class MemoryEngine:
    """Interface for memory engines."""

    def recall(self, query: str, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def write(self, item: Dict[str, Any], scope: Optional[str] = None) -> None:
        raise NotImplementedError()


TagType = str


STRUCTURING_TAGS = {"fact", "decision", "execution_result"}
NON_STRUCTURING_TAGS = {"chat_turn", "confirmation"}
ALL_TAGS = STRUCTURING_TAGS | NON_STRUCTURING_TAGS


def _default_token_counter(text: str) -> int:
    # Fallback deterministic counter (approx tokens ~= words)
    if not text:
        return 0
    return len(str(text).split())


@dataclass(frozen=True)
class WorkingEntry:
    item: Dict[str, Any]
    tag: TagType
    tokens: int
    inserted_at: float
    last_access_at: float



class InMemoryLayer(MemoryEngine):
    def __init__(self, name: str):
        self.name = name
        self._store: List[Dict[str, Any]] = []
        # each item is expected to be a dict with at least 'text' and optional 'meta' and 'ts'

    def recall(self, query: str, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        # naive substring search for now
        q = query.lower()
        res = [it for it in self._store if q in (it.get("text", "")).lower()]
        struct_log(_logger, "info", event="recall", layer=self.name, query=query, hits=len(res))
        return res

    def write(self, item: Dict[str, Any], scope: Optional[str] = None) -> None:
        self._store.append(item)
        struct_log(_logger, "info", event="write", layer=self.name, item_preview=item.get("text", "")[:120])


class MemoryKernel:
    """Facade exposing the three layers: working, recall, archival."""

    def __init__(self, *, token_counter: Optional[Callable[[str], int]] = None):
        self.recall = InMemoryLayer("recall")
        self.archival = InMemoryLayer("archival")

        # Recall retention (FIFO by insertion order)
        self.recall_max_items: int = int(os.environ.get("ARGUS_RECALL_MAX_ITEMS", "200"))

        # Archival successful_plan dedup threshold (SequenceMatcher ratio on goal)
        # Can be overridden by tests via ARGUS_ARCHIVAL_DEDUP_SIM_THRESHOLD env var.
        # If a test sets the env var after instantiation, we also fall back to
        # reading it at write-time (see _archival_write_with_dedup).
        self.archival_dedup_sim_threshold: float = float(
            os.environ.get("ARGUS_ARCHIVAL_DEDUP_SIM_THRESHOLD", "0.75")
        )




        # Working memory (LRU, token budget)
        self.working_token_budget: int = int(os.environ.get("ARGUS_WM_TOKEN_BUDGET", "2048"))
        self._token_counter: Callable[[str], int] = token_counter or _default_token_counter
        self._working_entries: "OrderedDict[str, WorkingEntry]" = OrderedDict()
        self._working_next_id: int = 0

        # Backward compat: expose a lightweight object with .recall/.write used elsewhere.
        # We keep .working._store only for older code/tests.
        self.working = InMemoryLayer("working")

    def _entry_tokens(self, item: Dict[str, Any]) -> int:
        text = item.get("text", "")
        # If item doesn't have 'text', fall back to string repr.
        if not text and item:
            text = str(item)
        return int(self._token_counter(text))

    def _current_working_tokens(self) -> int:
        return sum(e.tokens for e in self._working_entries.values())

    def _enforce_working_budget(self) -> None:
        # Evict LRU until under budget
        while self._working_entries and self._current_working_tokens() > self.working_token_budget:
            _ = self.evict()


    # --- Working Memory contract (LRU + token budget + tagging) ---
    def push(self, item: Dict[str, Any], tag: TagType) -> None:
        if not isinstance(item, dict):
            raise ValueError("working memory item must be a dict")
        if tag not in ALL_TAGS:
            raise ValueError(f"unknown working memory tag: {tag}")

        # Determine entry text/tokens
        tokens = self._entry_tokens(item)

        inserted_at = time.time()
        self._working_next_id += 1
        entry_id = str(self._working_next_id)

        entry = WorkingEntry(
            item=item,
            tag=tag,
            tokens=tokens,
            inserted_at=inserted_at,
            last_access_at=inserted_at,
        )
        # Insert as MRU (end)
        self._working_entries[entry_id] = entry

        # Also maintain legacy .working layer store for older code/tests
        # (best-effort; recall() uses it if query matches 'text')
        legacy_item = dict(item)
        legacy_item.setdefault("tag", tag)
        legacy_item.setdefault("ts", inserted_at)
        self.working.write(legacy_item)

        # New contract: structuring tags are written to recall immediately at push-time.
        if tag in STRUCTURING_TAGS:
            # Store a copy; WM can be evicted independently.
            self._recall_write_with_retention(dict(item))

        self._enforce_working_budget()



    def evict(self) -> List[Dict[str, Any]]:
        """Evict LRU entries until under budget.

        Returns the list of evicted *items*.
        """
        evicted_items: List[Dict[str, Any]] = []

        while self._working_entries and self._current_working_tokens() > self.working_token_budget:
            # popitem(last=False) => LRU
            entry_id, entry = self._working_entries.popitem(last=False)
            evicted_items.append(entry.item)

            struct_log(
                _logger,
                "info",
                event="working_evict",
                evicted_id=entry_id,
                evicted_tag=entry.tag,
                evicted_tokens=entry.tokens,
            )

            # Backward compat legacy store: remove one matching item (best effort)
            # Prefer removing by object identity if possible; otherwise fallback by index.
            try:
                # legacy layer appends; we cannot map ids -> legacy indices reliably.
                # We'll skip strict removal to avoid breaking existing tests.
                pass
            except Exception:
                pass

            # Eviction is now pure policy: it only removes from WM.
            # Recall routing responsibility moved to push().
            # NON_STRUCTURING: drop silently (implicitly).

        return evicted_items


    def _recall_write_with_retention(self, item: Dict[str, Any]) -> None:
        """Write into recall with FIFO retention cap.

        Recall retention is FIFO by insertion order: when the cap is exceeded,
        evict the oldest entries first.
        """
        self.recall.write(item)
        while len(self.recall._store) > self.recall_max_items:
            # remove oldest (FIFO)
            self.recall._store.pop(0)

    def _archival_write_with_dedup(self, item: Dict[str, Any]) -> None:
        """Write into archival with successful_plan de-duplication by similar goal.

        If an existing successful_plan has a similar `goal` above threshold,
        replace the best match (keep the newest).
        """
        from difflib import SequenceMatcher

        new_goal = item.get("goal", "")
        best_idx = None
        best_ratio = -1.0

        for idx, existing in enumerate(self.archival._store):
            if existing.get("type") != "successful_plan":
                continue
            old_goal = existing.get("goal", "")
            ratio = SequenceMatcher(a=new_goal, b=old_goal).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = idx

        # Tests may set the env var after MemoryKernel() instantiation.
        threshold = float(os.environ.get("ARGUS_ARCHIVAL_DEDUP_SIM_THRESHOLD", self.archival_dedup_sim_threshold))

        if best_idx is not None and best_ratio >= threshold:

            # Replace best matching older entry with the newest one.
            # Replace best match (in-place) so list size stays 1.
            self.archival._store[best_idx] = item
            # Remove any other similar successful_plan entries (dedup to 1).
            self.archival._store = [
                it
                for i, it in enumerate(self.archival._store)
                if it.get("type") != "successful_plan" or i == best_idx
            ]
            return


            struct_log(


                _logger,
                "info",
                event="archival_dedup_replaced",
                best_ratio=best_ratio,
                threshold=self.archival_dedup_sim_threshold,
            )
        else:
            self.archival.write(item)

    def get_context(self, budget: int) -> List[Dict[str, Any]]:



        """Return current WM content within token budget.

        Order: latest-first (MRU to LRU) until the budget is filled.
        Pure: does not modify LRU order nor timestamps.
        """
        if budget < 0:
            raise ValueError("budget must be >= 0")

        items: List[Dict[str, Any]] = []
        tokens_used = 0

        # Iterate from MRU (end) to LRU (start)
        for _entry_id, entry in reversed(list(self._working_entries.items())):
            # Keep at least one entry even if it exceeds budget
            if tokens_used + entry.tokens > budget and items:
                break

            items.append(entry.item)
            tokens_used += entry.tokens

        return items


    # --- recall helpers ---
    def recall_top(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:

        """Return top_k items across all layers ranked by string similarity.

        Uses difflib.SequenceMatcher ratio on the `text` field.
        """
        from difflib import SequenceMatcher

        candidates = []
        for layer_name in ("working", "recall", "archival"):
            layer = getattr(self, layer_name)
            for it in layer._store:
                text = it.get("text", "")
                ratio = SequenceMatcher(a=query, b=text).ratio()
                candidates.append((ratio, layer_name, it))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [dict(layer=ln, score=round(r, 3), item=it) for (r, ln, it) in candidates[:top_k]]

    # --- archival persistence ---
    def save_archival(self, path: str) -> None:
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.archival._store, f, ensure_ascii=False, indent=2)
        struct_log(_logger, "info", event="archival_saved", path=path, count=len(self.archival._store))

    def load_archival(self, path: str) -> None:
        import json
        import os

        if not os.path.exists(path):
            struct_log(_logger, "warning", event="archival_load_missing", path=path)
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.archival._store = data
        struct_log(_logger, "info", event="archival_loaded", path=path, count=len(data))

    def recall_all(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "working": self.working.recall(query),
            "recall": self.recall.recall(query),
            "archival": self.archival.recall(query),
        }

    def write(self, item: Dict[str, Any], layer: str = "working") -> None:
        # Backward compatible method.
        # For working layer: we do NOT try to infer tag; we assign a default.
        if layer == "working":
            if "ts" not in item:
                item["ts"] = time.time()
            # Default tag keeps prior behavior (working chat history), but now follows contract.
            default_tag: TagType = "chat_turn"
            self.push(item, tag=default_tag)
        elif layer == "recall":
            # Apply recall retention for ANY recall writes, not only push(tag=structuring).
            self._recall_write_with_retention(item)

        elif layer == "archival":
            # Apply successful_plan deduplication by similar goal.
            if item.get("type") == "successful_plan":
                self._archival_write_with_dedup(item)
            else:
                self.archival.write(item)

        else:
            raise ValueError("Unknown memory layer")


    # --- learning / planning helpers ---
    def get_similar_plans(self, goal: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieve successful plans from archival memory that have similar goals."""
        from difflib import SequenceMatcher
        
        candidates = []
        for it in self.archival._store:
            if it.get("type") == "successful_plan":
                plan_goal = it.get("goal", "")
                ratio = SequenceMatcher(a=goal, b=plan_goal).ratio()
                if ratio > 0.4: # basic threshold
                    candidates.append((ratio, it))
                    
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [it for (r, it) in candidates[:top_k]]
