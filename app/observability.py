"""Local-first audit trail for ARGUS runtime events."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class AuditLog:
    def __init__(self, path: str, max_events: int = 500):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_events = max_events
        self._events: deque[Dict[str, Any]] = deque(maxlen=max_events)
        self._lock = Lock()
        self._load_tail()

    def _load_tail(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-self.max_events:]
            for line in lines:
                if line.strip():
                    self._events.append(json.loads(line))
        except (OSError, ValueError):
            self._events.clear()

    def record(self, event: str, **data: Any) -> Dict[str, Any]:
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        with self._lock:
            self._events.append(item)
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            except OSError:
                # Observability must never break the user-facing operation.
                pass
        return item

    def recent(self, limit: int = 50, event: Optional[str] = None) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 100))
        items = list(self._events)
        if event:
            items = [item for item in items if item.get("event") == event]
        return list(reversed(items[-limit:]))
