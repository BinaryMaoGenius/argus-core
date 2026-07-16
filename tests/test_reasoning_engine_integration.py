import app.main as main_mod
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_plan_path_integration_when_needs_planning(monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "reasoning_engine",
        type(
            "R",
            (),
            {
                "decide": staticmethod(lambda goal, context=None: {
                    "type": "plan",
                    "plan": None,
                    "direct_answer": None,
                    "clarification_question": None,
                })
            },
        )(),
    )
    monkeypatch.setattr(
        main_mod.planning_engine,
        "generate_plan",
        lambda goal: [{"id": "step-1", "type": "noop", "async_group": 0}],
    )

    response = client.post("/plan", json={"goal": "Inspect the project"})
    assert response.status_code == 200
    body = response.json()

    assert body["type"] == "plan"
    assert body["plan"][0]["id"] == "step-1"
    assert body["direct_answer"] is None
    assert body["clarification_question"] is None


def test_direct_answer_path_integration(monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "reasoning_engine",
        type(
            "R",
            (),
            {
                "decide": staticmethod(lambda goal, context=None: {
                    "type": "direct_answer",
                    "plan": None,
                    "direct_answer": "Réponse directe",
                    "clarification_question": None,
                })
            },
        )(),
    )

    response = client.post("/plan", json={"goal": "hello"})
    assert response.status_code == 200
    body = response.json()

    assert body["type"] == "direct_answer"
    assert body["plan"] is None
    assert body["direct_answer"] == "Réponse directe"
    assert body["clarification_question"] is None


def test_clarification_path_integration(monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "reasoning_engine",
        type(
            "R",
            (),
            {
                "decide": staticmethod(lambda goal, context=None: {
                    "type": "clarification",
                    "plan": None,
                    "direct_answer": None,
                    "clarification_question": "Question ?",
                })
            },
        )(),
    )

    response = client.post("/plan", json={"goal": "do it"})
    assert response.status_code == 200
    body = response.json()

    assert body["type"] == "clarification"
    assert body["plan"] is None
    assert body["direct_answer"] is None
    assert body["clarification_question"] == "Question ?"

