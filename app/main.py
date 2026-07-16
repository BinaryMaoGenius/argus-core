from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import json
import uvicorn
import os
import time
import uuid

from .model_adapter import OllamaModelProvider
from .router import route_decide
from .memory.memory import MemoryKernel
from .security import SecurityEngine
from .engines.verification import VerificationEngine
from .engines.reflection import ReflectionEngine
from .observability import AuditLog
from .engines.planning import PlanningEngine
from .engines.execution import ExecutionEngine
from .engines.reasoning import ReasoningEngine
from .tools import registry


app = FastAPI(title="ARGUS Core API", version="0.2.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
FRONTEND_DIST_DIR = os.path.join(FRONTEND_DIR, ".output", "public")
ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
INDEX_HTML_PATH = os.path.join(FRONTEND_DIST_DIR, "index.html")
ARGUS_UI_PATH = os.path.join(FRONTEND_DIR, "argus_ui.html")
ARCHIVE_DIR = os.path.abspath(os.environ.get("ARGUS_ARCHIVE_DIR", os.path.join(BASE_DIR, "..", "data")))
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def _safe_archive_path(value: str) -> str:
    name = os.path.basename(str(value or ""))
    if name != str(value) or name in {".", ".."} or not name.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Archive name must be a JSON filename inside ARGUS_ARCHIVE_DIR")
    candidate = os.path.realpath(os.path.join(ARCHIVE_DIR, name))
    if os.path.commonpath([ARCHIVE_DIR, candidate]) != ARCHIVE_DIR:
        raise HTTPException(status_code=400, detail="Invalid archive path")
    return candidate

# Singleton instances
model_provider = OllamaModelProvider(base_url="http://localhost:11434")
memory_kernel = MemoryKernel()
security_engine = SecurityEngine()
planning_engine = PlanningEngine(model_provider, memory_kernel)
reasoning_engine = ReasoningEngine(model_provider)

execution_engine = ExecutionEngine(security_engine, memory_kernel)
verification_engine = VerificationEngine(security_engine)
reflection_engine = ReflectionEngine()

audit_log = AuditLog(os.environ.get("ARGUS_AUDIT_PATH", os.path.join(ARCHIVE_DIR, "audit.jsonl")))

# CORS â€” autorise le navigateur Ã  appeler l'API depuis le fichier HTML local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get("ARGUS_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/ping")
async def ping():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Prefer the non-SPA HTML UI (argus_ui.html) to ensure the GUI always renders.
    # The SPA bundle (index.html from frontend/.output/public) can fail at runtime
    # (e.g. Invariant failed) and would leave a blank page.
    if os.path.exists(ARGUS_UI_PATH):
        print(f"Serving argus_ui.html from {ARGUS_UI_PATH}")
        return FileResponse(ARGUS_UI_PATH, headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"})
    if os.path.exists(INDEX_HTML_PATH):
        print(f"Serving index.html from {INDEX_HTML_PATH}")
        return FileResponse(INDEX_HTML_PATH)


    return HTMLResponse("""
    <!doctype html>
    <html lang='fr'>
      <head><meta charset='utf-8'><title>COS MVP</title></head>
      <body style='font-family: Arial; margin: 2rem;'>
        <h1>COS MVP</h1>
        <p>Le frontend est en cours dâ€™intÃ©gration.</p>
        <p>Utilisez /ping pour vÃ©rifier lâ€™API.</p>
      </body>
    </html>
    """)



@app.get("/demo", response_class=HTMLResponse)
async def demo(request: Request):
    return await home(request)


@app.post("/decide")
async def decide(prompt: str):
    decision = route_decide(prompt, detailed=True)
    return {"path": decision["path"], "model": decision["model"], "reason": decision["reason"]}


@app.post("/memory/write")
async def memory_write(payload: Dict[str, Any]):
    text = payload.get("text")
    layer = payload.get("layer", "working")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text must be a non-empty string")
    if layer not in {"working", "recall", "archival"}:
        raise HTTPException(status_code=400, detail="invalid memory layer")
    memory_kernel.write({"text": text}, layer=layer)
    return {"ok": True, "layer": layer}


@app.get("/memory/recall")
async def memory_recall(q: str, top_k: int = 5):
    if top_k < 1 or top_k > 50:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 50")
    res = memory_kernel.recall_top(q, top_k=top_k)
    return {"query": q, "results": res}


@app.post("/memory/save")
async def memory_save(payload: Dict[str, Any]):
    path = payload.get("path")
    if not path:
        return {"error": "missing path"}
    safe_path = _safe_archive_path(path)
    memory_kernel.save_archival(safe_path)
    return {"saved": True, "path": os.path.basename(safe_path)}


@app.post("/memory/load")
async def memory_load(payload: Dict[str, Any]):
    path = payload.get("path")
    if not path:
        return {"error": "missing path"}
    safe_path = _safe_archive_path(path)
    memory_kernel.load_archival(safe_path)
    return {"loaded": True, "path": os.path.basename(safe_path)}


class PlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)


class ExecuteRequest(BaseModel):
    plan: List[Dict[str, Any]] = Field(min_length=1, max_length=30)
    confirm: bool = False
    goal: str = ""


def _validate_plan(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid_types = {"noop", "shell", "tool"}
    known_tools = set(registry.list_tools())
    normalized = []
    for index, action in enumerate(plan):
        if not isinstance(action, dict):
            raise HTTPException(status_code=400, detail=f"plan action {index} must be an object")
        action_type = action.get("type", "noop")
        if action_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"unsupported action type: {action_type}")
        item = dict(action)
        item["id"] = str(item.get("id", index))
        item["async_group"] = int(item.get("async_group", index))
        if action_type == "shell":
            if not isinstance(item.get("cmd"), str) or not item["cmd"].strip():
                raise HTTPException(status_code=400, detail=f"shell action {item['id']} requires cmd")
        if action_type == "tool":
            if item.get("tool") not in known_tools:
                raise HTTPException(status_code=400, detail=f"unknown tool: {item.get('tool')}")
            if not isinstance(item.get("payload", {}), dict):
                raise HTTPException(status_code=400, detail=f"tool action {item['id']} payload must be an object")
        normalized.append(item)
    return normalized


@app.post("/plan")
async def create_plan(payload: PlanRequest):
    # Backward compatible endpoint: always generate a plan.
    # ReasoningEngine integration will be handled in a dedicated branch/ticket.
    plan = _validate_plan(planning_engine.generate_plan(payload.goal))

    if plan:
        memory_kernel.push({"goal": payload.goal, "plan": plan}, tag="decision")
    verification = verification_engine.verify_plan(plan)

    audit_log.record(
        "plan.created",
        goal=payload.goal,
        steps=len(plan),
        status=verification["status"],
        confidence=verification["confidence"],
    )
    return {
        "type": "plan",
        "status": verification["status"],
        "goal": payload.goal,
        "plan": plan,
        "direct_answer": None,
        "clarification_question": None,
        "verification": verification,
        "requires_confirmation": verification["requires_confirmation"],
        # Backward compat: some clients/tests expect top-level "status" only.
    }




@app.post("/execute")
async def execute_plan(payload: ExecuteRequest):
    plan = _validate_plan(payload.plan)
    verification = verification_engine.verify_plan(plan)
    if verification["status"] == "blocked":
        audit_log.record("execution.blocked", reason="verification", steps=len(plan))
        raise HTTPException(status_code=400, detail={"status": "blocked", "verification": verification})
    if not payload.confirm:
        audit_log.record(
            "execution.pending_confirmation",
            goal=payload.goal,
            steps=len(plan),
            confidence=verification["confidence"],
        )
        raise HTTPException(
            status_code=409,
            detail={
                "status": "pending_confirmation",
                "requires_confirmation": True,
                "plan": plan,
                "verification": verification,
            },
        )
    execution_id = uuid.uuid4().hex
    started = time.perf_counter()
    results = await execution_engine.execute_plan(plan, confirmed=True)
    reflection = reflection_engine.reflect(execution_id, plan, results, time.perf_counter() - started)
    if reflection["success"] and payload.goal:
        memory_kernel.write(
            {"type": "successful_plan", "goal": payload.goal, "plan": plan, "execution_id": execution_id},
            layer="archival",
        )
    audit_log.record(
        "execution.completed" if reflection["success"] else "execution.failed",
        execution_id=execution_id,
        goal=payload.goal,
        success=reflection["success"],
        duration_s=reflection["duration_s"],
        tasks_total=reflection["tasks_total"],
        tasks_failed=reflection["tasks_failed"],
    )
    return {
        "status": "executed",
        "execution_id": execution_id,
        "verification": verification,
        "reflection": reflection,
        "results": results,
    }

@app.get("/events")
async def list_events(limit: int = 50, event: str | None = None):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return {"events": audit_log.recent(limit=limit, event=event)}


@app.get("/executions")
async def list_executions(limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    events = audit_log.recent(limit=100)
    executions = [
        item for item in events
        if item.get("event") in {"execution.completed", "execution.failed", "execution.blocked"}
    ]
    return {"executions": executions[:limit]}

# --- Prefix-Stable Prompt Configuration ---
SYSTEM_PROMPT = (
    "You are ARGUS, a local-first cognitive operations system. "
    "Respond clearly and precisely. If the user's request is ambiguous, incomplete, or lacks sufficient detail, "
    "ask one or two concise clarifying questions before proceeding. "
    "Do not assume missing requirements, and always prefer a safer, clearer response."
)

def build_prefix_stable_prompt(new_prompt: str, history: list) -> str:
    """Builds a prompt where the prefix (system + history) is stable to maximize KV-cache reuse."""
    context = f"SYSTEM: {SYSTEM_PROMPT}\n"
    for item in history:
        role = item.get("role", "User")
        text = item.get("text", "")
        context += f"{role}: {text}\n"
    return context + f"User: {new_prompt}\nAssistant:"

@app.post("/generate")
async def generate(payload: Dict[str, Any]):
    model = payload.get("model") or os.environ.get("ARGUS_EXECUTION_MODEL", "qwen2.5:7b")
    prompt = payload.get("prompt")
    num_predict = int(payload.get("num_predict", 80))
    keep_alive = payload.get("keep_alive", "10m")
    if not prompt:
        return {"error": "missing prompt"}
        
    history = memory_kernel.working.recall("")
    full_prompt = build_prefix_stable_prompt(prompt, history)

    data = model_provider.generate(model, full_prompt, num_predict=num_predict, keep_alive=keep_alive)
    
    memory_kernel.write({"role": "User", "text": prompt}, layer="working")
    memory_kernel.write({"role": "Assistant", "text": data.get("response", "")}, layer="working")
    
    return data


@app.post("/generate/stream")
async def generate_stream(payload: Dict[str, Any]):
    prompt = payload.get("prompt")
    if not prompt:
        return {"error": "missing prompt"}

    decision = route_decide(prompt, detailed=True)
    model = payload.get("model") or decision["model"]
    num_predict = int(payload.get("num_predict", 80))
    keep_alive = payload.get("keep_alive", "10m")

    history = memory_kernel.working.recall("")
    full_prompt = build_prefix_stable_prompt(prompt, history)

    def event_stream():
        t_start = time.perf_counter()
        t_first_token = None
        token_count = 0
        full_response = ""

        yield json.dumps({"type": "routing", "path": decision["path"], "model": model, "reason": decision["reason"]}, ensure_ascii=False) + "\n"

        for chunk in model_provider.stream_generate(model, full_prompt, num_predict=num_predict, keep_alive=keep_alive):
            if t_first_token is None and chunk.get("response"):
                t_first_token = time.perf_counter()
            if chunk.get("response"):
                token_count += 1
                full_response += chunk["response"]
            yield json.dumps(chunk, ensure_ascii=False) + "\n"

        t_end = time.perf_counter()
        
        memory_kernel.write({"role": "User", "text": prompt}, layer="working")
        memory_kernel.write({"role": "Assistant", "text": full_response}, layer="working")
        
        yield json.dumps({
            "type": "metrics",
            "time_to_first_token_s": round(t_first_token - t_start, 3) if t_first_token is not None else None,
            "total_time_s": round(t_end - t_start, 3),
            "approx_tokens": token_count,
        }, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    print("Starting COS API on http://127.0.0.1:8000")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)












