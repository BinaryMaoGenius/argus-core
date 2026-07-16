import json
import os
from typing import Dict, Any, List
from ..logging import get_logger, struct_log
from ..model_adapter import ModelProvider
from ..memory.memory import MemoryKernel

_logger = get_logger("planning")

class PlanningEngine:
    """Planning Engine using Skeleton-of-Thought and Few-Shot learning.
    
    Generates a fast, JSON-only sequence of actions (sub-tasks).
    """
    def __init__(self, model_provider: ModelProvider, memory_kernel: MemoryKernel, model_name: str = os.getenv("ARGUS_EXECUTION_MODEL", "qwen2.5:14b")):
        self.model_provider = model_provider
        self.memory = memory_kernel
        self.model_name = model_name

    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        struct_log(_logger, "info", event="planning_start", goal=goal)
        
        # 1. Dynamic Few-Shot (Learning Engine basic integration)
        # Fetch successful past plans from archival memory if any
        similar_plans = self.memory.get_similar_plans(goal)
        few_shot_context = ""
        if similar_plans:
            few_shot_context = "Here are similar successful plans you have executed in the past:\n"
            for plan in similar_plans:
                few_shot_context += f"Goal: {plan['goal']}\nPlan: {json.dumps(plan['plan'])}\n\n"

        # 2. Skeleton-of-Thought Prompt
        prompt = f"""SYSTEM: You are the Planning Engine of COS.
Your ONLY job is to output a JSON array of task objects to achieve the goal.
Do NOT output any explanations, markdown formatting, or thought processes. Output STRICT JSON ONLY.

A task object has:
- "id": string (unique)
- "type": "tool" or "shell"
- "tool": tool name (if type is tool)
- "payload": tool arguments (if type is tool)
- "cmd": shell command string (if type is shell)
- "async_group": int (tasks with the same async_group can be executed in parallel, otherwise sequential)

{few_shot_context}
USER GOAL: {goal}
PLAN (JSON ARRAY):"""

        # 3. Generate with strict JSON format
        data = self.model_provider.generate(
            self.model_name, 
            prompt, 
            num_predict=300, 
            response_format="json"
        )
        
        raw_response = data.get("response", "[]")
        struct_log(_logger, "info", event="planning_raw_response", response=raw_response)
        
        try:
            plan = json.loads(raw_response)
            if not isinstance(plan, list):
                plan = []
        except json.JSONDecodeError:
            struct_log(_logger, "error", event="planning_parse_error", response=raw_response)
            plan = []
            
        struct_log(_logger, "info", event="planning_success", steps=len(plan))
        return plan

