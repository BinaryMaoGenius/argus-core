"""Post-execution reflection for ARGUS."""
from __future__ import annotations

from typing import Any, Dict, List


class ReflectionEngine:
    """Turns raw execution results into an auditable outcome."""

    def __init__(self, memory_kernel=None):
        self.memory = memory_kernel


    SUCCESS_STATUSES = {"ok", "executed", "tool_executed"}

    def reflect(
        self,
        execution_id: str,
        plan: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        duration_s: float,
    ) -> Dict[str, Any]:
        failed = [item for item in results if item.get("status") not in self.SUCCESS_STATUSES]
        success = not failed and len(results) == len(plan)
        if success:
            lesson = "Plan exécuté sans erreur observable."
            cause = None
        else:
            lesson = "Le plan doit être révisé avant une nouvelle tentative."
            cause = failed[0].get("reason") or failed[0].get("error") if failed else "Résultat incomplet"

        reflection = {
            "execution_id": execution_id,
            "success": success,
            "duration_s": round(duration_s, 3),
            "tasks_total": len(plan),
            "tasks_completed": len(results) - len(failed),
            "tasks_failed": len(failed),
            "probable_cause": cause,
            "lesson": lesson,
            "results": results,
        }

        if self.memory is not None:
            # fact: push in all cases (success/failure)
            self.memory.push(
                item={
                    "success": reflection.get("success"),
                    "execution_id": reflection.get("execution_id"),
                    "duration_s": reflection.get("duration_s"),
                    "tasks_total": reflection.get("tasks_total"),
                    "tasks_failed": reflection.get("tasks_failed"),
                    "probable_cause": reflection.get("probable_cause", None),
                    "lesson": reflection.get("lesson", None),
                },
                tag="fact",
            )

        return reflection

