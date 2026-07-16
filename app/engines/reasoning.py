"""Minimal reasoning engine for deciding between direct answer, planning, or clarification."""

from __future__ import annotations

from typing import Any, Dict, Optional
import os

from ..logging import get_logger, struct_log
from ..model_adapter import ModelProvider

_logger = get_logger("reasoning")


class ReasoningEngine:
    """A minimal front-end decision engine.

    It is intentionally stateless: it does not persist memory or keep internal state.
    """

    def __init__(self, model_provider: ModelProvider, model_name: Optional[str] = None):
        self.model_provider = model_provider
        self.model_name = model_name or os.environ.get("ARGUS_TRIAGE_MODEL", "qwen2.5:7b")

    def decide(self, goal: str, context: Any = None) -> Dict[str, Any]:
        """Decide pipeline path before Planning.

        Returns a discriminated union payload:
        {
          "type": "plan"|"direct_answer"|"clarification",
          "plan": list|null,
          "direct_answer": str|null,
          "clarification_question": str|null,
          # internal fields may exist but clients should rely on the discriminant.
        }
        """

        # Minimal safety/quality heuristics (cheap) to avoid unnecessary LLM calls.
        g = (goal or "").strip()
        if not g:
            return {
                "type": "clarification",
                "plan": None,
                "direct_answer": None,
                "clarification_question": "What would you like to accomplish?",
            }

        # Heuristic: very short greetings are best answered directly.
        if len(g) < 50 and any(w in g.lower() for w in ("bonjour", "salut", "hello", "hi", "merci", "thanks")):
            return {
                "type": "direct_answer",
                "plan": None,
                "direct_answer": "Bonjour ! Comment puis-je vous aider ?",
                "clarification_question": None,
            }

        # Otherwise ask a lightweight model for a strict JSON discriminant.
        # Keep prompt compact and JSON-only.
        ctx_hint = ""
        if context is not None:
            # Context is not required; keep short.
            ctx_hint = f"\nContext (optional): {str(context)[:800]}"

        prompt = f"""SYSTEM: You are ARGUS Reasoning Engine. Decide the best pipeline path before Planning.
You must output STRICT JSON ONLY.

Goal routing rules:
- type = "clarification" if the goal is ambiguous/incomplete. Provide exactly ONE concise clarification_question.
- type = "direct_answer" if the user can be answered directly without a structured plan. Provide a short direct_answer.
- type = "plan" if a structured set of actions is required. Set plan to null and both other fields to null.

Return this JSON schema exactly:
{{
  "type": "plan" | "direct_answer" | "clarification",
  "plan": null | [],
  "direct_answer": null | string,
  "clarification_question": null | string
}}

If type == "plan": plan must be null; direct_answer and clarification_question must be null.
If type == "direct_answer": direct_answer is non-null; plan and clarification_question are null.
If type == "clarification": clarification_question is non-null; plan and direct_answer are null.

USER GOAL: {g}{ctx_hint}
"""

        try:
            data = self.model_provider.generate(
                self.model_name,
                prompt,
                num_predict=120,
                response_format="json",
            )
        except Exception:
            # Offline / tests: default to planning path without crashing.
            struct_log(_logger, "warning", event="reasoning_generate_failed_offline", goal=g)
            return {
                "type": "plan",
                "plan": None,
                "direct_answer": None,
                "clarification_question": None,
            }

        raw = data.get("response", "")

        try:
            import json

            parsed = json.loads(raw)
        except Exception:
            struct_log(_logger, "warning", event="reasoning_parse_failed", goal=g, raw=raw)
            return {
                "type": "plan",
                "plan": None,
                "direct_answer": None,
                "clarification_question": None,
            }

        # Normalize discriminant payload.
        t = parsed.get("type")
        if t not in {"plan", "direct_answer", "clarification"}:
            t = "plan"

        if t == "plan":
            return {
                "type": "plan",
                "plan": None,
                "direct_answer": None,
                "clarification_question": None,
            }
        if t == "direct_answer":
            return {
                "type": "direct_answer",
                "plan": None,
                "direct_answer": parsed.get("direct_answer") or "",
                "clarification_question": None,
            }
        return {
            "type": "clarification",
            "plan": None,
            "direct_answer": None,
            "clarification_question": parsed.get("clarification_question") or "",
        }

