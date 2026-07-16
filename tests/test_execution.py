import asyncio

from app.engines.execution import ExecutionEngine
from app.security import SecurityEngine


def test_execution_allows_safe_shell():
    sec = SecurityEngine()
    eng = ExecutionEngine(sec)
    plan = [{"id": 1, "type": "shell", "cmd": "echo hello"}]

    # monkeypatch subprocess.run to avoid actually running commands in tests
    import subprocess

    class DummyCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = "hello\n"
            self.stderr = ""

    def fake_run(*a, **k):
        return DummyCompleted()

    subprocess_run = subprocess.run
    subprocess.run = fake_run
    try:
        res = asyncio.run(eng.execute_plan(plan))
    finally:
        subprocess.run = subprocess_run

    assert res[0]["status"] == "executed"


def test_execution_blocks_destructive_shell():
    sec = SecurityEngine()
    eng = ExecutionEngine(sec)
    plan = [{"id": 2, "type": "shell", "cmd": "rm -rf /"}]
    res = asyncio.run(eng.execute_plan(plan))
    assert res[0]["status"] == "blocked"
    assert "Destructive" in res[0]["reason"]
