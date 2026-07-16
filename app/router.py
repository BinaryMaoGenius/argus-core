"""Simple router implementing triage rules for model selection."""
import re
import os

MODE_FAST = "fast"
MODE_SLOW = "slow"
MODE_TRiAGE = MODE_FAST
MODE_CODER = MODE_SLOW
MODEL_FAST = os.getenv("ARGUS_TRIAGE_MODEL", "qwen2.5:7b")
MODEL_SLOW = os.getenv("ARGUS_EXECUTION_MODEL", "qwen2.5:14b")

# Heuristics lists
COMPLEX_INTENT_KEYWORDS = r"(?i)\b(code|file|fichier|script|write|Ã©cris|plan|complex|analyse|read|lis|bug|erreur|error|debug|refactor)\b"
GREETING_INTENT_KEYWORDS = r"(?i)\b(hi|hello|bonjour|salut|merci|thanks|bye|au revoir)\b"

def route_decide(prompt: str, threshold: int = 150, detailed: bool = False):
    """Decide which model to use based on strict heuristics.
    
    This avoids calling a heavier LLM when a fast answer is sufficient.
    - Matches complex regex -> slow path (14B)
    - Matches greeting regex -> fast path (7B)
    - short prompts -> fast path (7B)
    - longer prompts -> slow path (14B)
    """
    if not prompt:
        decision = {"path": MODE_FAST, "model": MODEL_FAST, "reason": "empty prompt", "threshold": threshold}
    elif re.search(COMPLEX_INTENT_KEYWORDS, prompt):
        decision = {"path": MODE_SLOW, "model": MODEL_SLOW, "reason": "complex intent keyword detected", "threshold": threshold}
    elif re.search(GREETING_INTENT_KEYWORDS, prompt) and len(prompt) < 100:
        decision = {"path": MODE_FAST, "model": MODEL_FAST, "reason": "greeting intent detected", "threshold": threshold}
    elif len(prompt) <= threshold:
        decision = {"path": MODE_FAST, "model": MODEL_FAST, "reason": "short prompt", "threshold": threshold}
    else:
        decision = {"path": MODE_SLOW, "model": MODEL_SLOW, "reason": "complex prompt length", "threshold": threshold}

    if detailed:
        return decision
    return decision["path"]

