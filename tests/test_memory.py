from app.memory.memory import MemoryKernel


def test_memory_write_and_recall():
    m = MemoryKernel()
    m.write({"text": "This is a test item"}, layer="working")
    res = m.recall_all("test")
    assert len(res["working"]) == 1
    assert res["working"][0]["text"] == "This is a test item"
