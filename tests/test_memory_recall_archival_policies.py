import os
import pytest

from app.memory.memory import MemoryKernel


def test_recall_cap_fifo_applies_on_push_structuring(monkeypatch):
    monkeypatch.setenv("ARGUS_RECALL_MAX_ITEMS", "2")
    # reload kernel after env var change by creating a fresh instance
    m = MemoryKernel()

    # Ensure WM budget irrelevant
    m.working_token_budget = 10_000

    m.push({"text": "fact-1"}, tag="fact")
    m.push({"text": "fact-2"}, tag="fact")
    assert [it.get("text") for it in m.recall._store] == ["fact-1", "fact-2"]

    m.push({"text": "fact-3"}, tag="fact")
    # FIFO eviction: keep most recent 2
    assert [it.get("text") for it in m.recall._store] == ["fact-2", "fact-3"]


def test_recall_cap_fifo_applies_on_direct_recall_write(monkeypatch):
    monkeypatch.setenv("ARGUS_RECALL_MAX_ITEMS", "1")
    m = MemoryKernel()
    m.working_token_budget = 10_000

    m.write({"text": "r1"}, layer="recall")
    m.write({"text": "r2"}, layer="recall")
    assert [it.get("text") for it in m.recall._store] == ["r2"]


def test_archival_dedup_replaces_best_goal_match(monkeypatch):
    monkeypatch.setenv("ARGUS_ARCHIVAL_DEDUP_SIM_THRESHOLD", "0.75")
    m = MemoryKernel()

    old = {
        "type": "successful_plan",
        "goal": "List files in a directory",
        "execution_id": "old",
        "plan": [{"id": "a", "type": "noop"}],
    }
    m.write(old, layer="archival")

    new = {
        "type": "successful_plan",
        "goal": "Show directory file listing",
        "execution_id": "new",
        "plan": [{"id": "b", "type": "noop"}],
    }

    # If similar enough, it should replace.
    m.write(new, layer="archival")

    items = [it for it in m.archival._store if it.get("type") == "successful_plan"]
    assert len(items) == 1
    assert items[0].get("execution_id") == "new"
    assert items[0].get("goal") == new["goal"]


def test_archival_dedup_below_threshold_appends(monkeypatch):
    monkeypatch.setenv("ARGUS_ARCHIVAL_DEDUP_SIM_THRESHOLD", "0.95")
    m = MemoryKernel()

    m.write(
        {
            "type": "successful_plan",
            "goal": "How to list files in Python",
            "execution_id": "old",
            "plan": [{"id": "a", "type": "noop"}],
        },
        layer="archival",
    )

    # Clearly different goal
    m.write(
        {
            "type": "successful_plan",
            "goal": "Explain OAuth vs SSO",
            "execution_id": "new",
            "plan": [{"id": "b", "type": "noop"}],
        },
        layer="archival",
    )

    items = [it for it in m.archival._store if it.get("type") == "successful_plan"]
    assert len(items) == 2
    assert {it.get("execution_id") for it in items} == {"old", "new"}

