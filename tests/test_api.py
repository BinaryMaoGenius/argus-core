import json
from fastapi.testclient import TestClient
import app.main as main_mod
from app.main import app

client = TestClient(app)


def test_memory_write_and_recall_api():
    main_mod.memory_kernel.working._store.clear()
    resp = client.post("/memory/write", json={"text": "List files in Python using os.listdir", "layer": "working"})
    assert resp.status_code == 200 and resp.json().get("ok")

    r = client.get("/memory/recall", params={"q": "list files", "top_k": 5})
    assert r.status_code == 200
    results = r.json()["results"]
    assert any("List files" in it["item"]["text"] for it in results)


def test_memory_save_load_api():
    main_mod.memory_kernel.archival._store.clear()
    resp = client.post("/memory/write", json={"text": "persist me", "layer": "archival"})
    assert resp.status_code == 200
    path = "test_arch.json"
    resp = client.post("/memory/save", json={"path": path})
    assert resp.status_code == 200

    main_mod.memory_kernel.archival._store = []
    resp = client.post("/memory/load", json={"path": path})
    assert resp.status_code == 200
    assert any("persist me" in it.get("text", "") for it in main_mod.memory_kernel.archival._store)


def test_generate_api_sync(monkeypatch):
    def fake_generate(model, prompt, num_predict=50, keep_alive="10m"):
        return {"response": "sync ok", "model": model, "prompt": prompt}

    monkeypatch.setattr(main_mod, "model_provider", type("X", (), {"generate": staticmethod(fake_generate)})())
    resp = client.post("/generate", json={"prompt": "hello", "model": "m"})
    assert resp.status_code == 200
    assert resp.json()["response"] == "sync ok"


def test_decide_introspection_endpoint():
    resp = client.post("/decide", params={"prompt": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] in {"fast", "slow"}
    assert body["model"]


def test_generate_stream_api(monkeypatch):
    def fake_stream(model, prompt, num_predict=50, keep_alive="10m"):
        yield {"response": "a", "done": False}
        yield {"response": "b", "done": True}

    monkeypatch.setattr(main_mod, "model_provider", type("X", (), {"stream_generate": staticmethod(fake_stream)})())
    resp = client.post("/generate/stream", json={"prompt": "p", "model": "m", "num_predict": 10})
    assert resp.status_code == 200
    lines = list(resp.iter_lines())
    parsed = [json.loads(l) for l in lines if l.strip()]
    assert any(d.get("type") == "routing" for d in parsed)
    assert any(d.get("response") == "a" for d in parsed)
    assert any(d.get("response") == "b" for d in parsed)
    assert any(d.get("type") == "metrics" for d in parsed)


def test_memory_input_contracts():
    assert client.post("/memory/write", json={"text": "", "layer": "working"}).status_code == 400
    assert client.post("/memory/write", json={"text": "x", "layer": "unknown"}).status_code == 400
    assert client.get("/memory/recall", params={"q": "x", "top_k": 51}).status_code == 400


def test_archive_path_is_confined():
    assert client.post("/memory/save", json={"path": "../outside.json"}).status_code == 400
    assert client.post("/memory/save", json={"path": "contract_check.json"}).status_code == 200


def test_supervised_execution_requires_confirmation():
    plan = [{"id": "safe", "type": "noop"}]
    pending = client.post("/execute", json={"plan": plan, "confirm": False})
    assert pending.status_code == 409
    assert pending.json()["detail"]["verification"]["status"] == "verified"

    executed = client.post("/execute", json={"plan": plan, "confirm": True, "goal": "safe noop"})
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    assert executed.json()["reflection"]["success"] is True
    assert executed.json()["execution_id"]


def test_plan_endpoint_returns_pending_plan(monkeypatch):
    monkeypatch.setattr(
        main_mod.planning_engine,
        "generate_plan",
        lambda goal: [{"id": "step-1", "type": "noop", "async_group": 0}],
    )
    response = client.post("/plan", json={"goal": "Inspect the project"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["requires_confirmation"] is False
    assert body["verification"]["status"] == "verified"
    assert body["plan"][0]["id"] == "step-1"


def test_plan_rejects_malformed_shell_action():
    response = client.post(
        "/execute",
        json={"plan": [{"type": "shell", "cmd": ""}], "confirm": True},
    )
    assert response.status_code == 400


def test_verification_blocks_disallowed_shell():
    response = client.post(
        "/execute",
        json={"plan": [{"id": "danger", "type": "shell", "cmd": "rm -rf /"}], "confirm": True},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["status"] == "blocked"


def test_observability_endpoints():
    events = client.get("/events", params={"limit": 20})
    assert events.status_code == 200
    assert isinstance(events.json()["events"], list)
    executions = client.get("/executions", params={"limit": 20})
    assert executions.status_code == 200
    assert any(item["event"] == "execution.completed" for item in executions.json()["executions"])
    assert client.get("/events", params={"limit": 101}).status_code == 400
