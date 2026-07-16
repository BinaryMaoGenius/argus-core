"""Risk and confidence assessment for supervised ARGUS plans."""
from __future__ import annotations

from typing import Any, Dict, List
from ..security import SecurityEngine


class VerificationEngine:
    """Builds a compact belief record before a plan can be executed."""

    def __init__(self, security: SecurityEngine):
        self.security = security

    def verify_plan(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        beliefs = []
        risks = []
        confidence = 1.0
        requires_confirmation = False

        for action in plan:
            action_id = str(action.get("id"))
            action_type = action.get("type", "noop")

            if action_type == "noop":
                beliefs.append({
                    "id": action_id,
                    "belief": "No system side effect detected",
                    "classification": "known",
                    "confidence": 0.99,
                    "requires_confirmation": False,
                })
                continue

            if action_type == "shell":
                policy = self.security.allow_action(str(action.get("cmd", "")), kind="shell")
                if not policy["allowed"]:
                    risks.append({"id": action_id, "level": "blocked", "reason": policy["reason"]})
                    beliefs.append({
                        "id": action_id,
                        "belief": "Shell command is not permitted by current policy",
                        "classification": "blocked",
                        "confidence": 0.99,
                        "requires_confirmation": False,
                    })
                    return {
                        "status": "blocked",
                        "confidence": 0.0,
                        "beliefs": beliefs,
                        "risks": risks,
                        "requires_confirmation": False,
                    }
                score = 0.75
                requires_confirmation = True
                risks.append({"id": action_id, "level": "medium", "reason": "Host command execution"})
                belief = "Allowlisted shell command; host effect remains possible"
            elif action_type == "tool":
                tool_name = str(action.get("tool", ""))
                policy = self.security.allow_action(tool_name)
                score = 0.95 if tool_name == "read_file" else 0.65
                requires_confirmation = True
                risks.append({"id": action_id, "level": "high" if tool_name != "read_file" else "low", "reason": tool_name})
                belief = f"Tool '{tool_name}' is registered; payload requires review"
                if not policy["allowed"] and tool_name not in {"write_file", "search_and_replace"}:
                    return {
                        "status": "blocked",
                        "confidence": 0.0,
                        "beliefs": beliefs,
                        "risks": risks,
                        "requires_confirmation": False,
                    }
            else:
                continue

            confidence = min(confidence, score)
            beliefs.append({
                "id": action_id,
                "belief": belief,
                "classification": "inferred",
                "confidence": score,
                "requires_confirmation": True,
            })

        return {
            "status": "needs_confirmation" if requires_confirmation else "verified",
            "confidence": round(confidence, 2),
            "beliefs": beliefs,
            "risks": risks,
            "requires_confirmation": requires_confirmation,
        }
