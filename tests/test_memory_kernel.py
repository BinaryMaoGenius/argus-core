import os
import tempfile

from app.memory.memory import ALL_TAGS, MemoryKernel, STRUCTURING_TAGS


def test_working_eviction_by_token_budget():
    m = MemoryKernel(token_counter=lambda s: len(str(s).split()))
    # set small budget to force eviction
    m.working_token_budget = 10
    # three items of 6 tokens each => total 18 => should evict oldest until <=10
    m.push({"text": "one two three four five six"}, tag="chat_turn")

    m.push({"text": "alpha beta gamma delta epsilon zeta"}, tag="chat_turn")
    m.push({"text": "uno dos tres cuatro cinco seis"}, tag="chat_turn")

    assert m._current_working_tokens() <= m.working_token_budget


def test_working_lru_order_eviction():
    m = MemoryKernel(token_counter=lambda s: len(str(s).split()))
    m.working_token_budget = 10
    # A then B then touch A (so B becomes LRU), then push C to force eviction
    m.push({"text": "a1 a2 a3 a4 a5"}, tag="chat_turn")  # 5 tokens
    m.push({"text": "b1 b2 b3 b4 b5"}, tag="chat_turn")  # 5 tokens
    # Access via get_context must be PURE: it must NOT refresh LRU.
    # So A remains older than B, and pushing C should evict A (LRU).
    _ = m.get_context(budget=10)
    m.push({"text": "c1 c2 c3 c4 c5"}, tag="chat_turn")


    ctx = [it.get("text") for it in m.get_context(budget=10)]
    assert "a1 a2 a3 a4 a5" not in ctx
    assert "b1 b2 b3 b4 b5" in ctx
    assert "c1 c2 c3 c4 c5" in ctx



def test_push_routes_structuring_to_recall_immediately():
    m = MemoryKernel(token_counter=lambda s: len(str(s).split()))
    m.working_token_budget = 100  # no eviction

    m.push({"text": "fact one two three four five"}, tag="fact")

    recall_texts = [it.get("text") for it in m.recall._store]
    assert "fact one two three four five" in recall_texts


def test_non_structuring_never_in_recall_even_if_evicted():
    m = MemoryKernel(token_counter=lambda s: len(str(s).split()))
    m.working_token_budget = 10

    m.push({"text": "chat a b c d e"}, tag="chat_turn")  # 5 tokens
    m.push({"text": "chat f g h i j"}, tag="chat_turn")  # 5 tokens -> total 10
    m.push({"text": "chat k l m n o"}, tag="chat_turn")  # 5 tokens -> should evict LRU

    # Non-structuring item should never appear in recall
    recall_texts = [it.get("text") for it in m.recall._store]
    assert "chat a b c d e" not in recall_texts





def test_recall_top_ranking():
    m = MemoryKernel()
    m.write({"text": "How to list files in Python"}, layer="working")
    m.write({"text": "Django IntegrityError debugging tips"}, layer="recall")
    m.write({"text": "Filesystem operations rm and delete"}, layer="archival")

    top = m.recall_top("list files python", top_k=2)
    assert len(top) == 2
    assert top[0]["layer"] in ("working", "recall", "archival")


def test_archival_save_load_tmpfile():
    m = MemoryKernel()
    m.write({"text": "persist me"}, layer="archival")
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        m.save_archival(path)
        # create new kernel and load
        m2 = MemoryKernel()
        m2.load_archival(path)
        assert len(m2.archival._store) >= 1
        assert any("persist me" in it.get("text", "") for it in m2.archival._store)
    finally:
        os.remove(path)
