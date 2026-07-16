from typing import Dict, Any, Optional
from ..security import SecurityEngine
from . import registry
from ..logging import get_logger, struct_log

_logger = get_logger("tool_engine")

class ToolEngine:
    """Orchestrates tool invocation, routing requests through the SecurityEngine."""
    
    def __init__(self, security_engine: SecurityEngine):
        self.security_engine = security_engine

    def execute_tool(self, name: str, payload: Dict[str, Any], require_confirmation: bool = True) -> Dict[str, Any]:
        """Execute a tool by name, optionally requiring human confirmation for side-effects."""
        try:
            tool = registry.get_tool(name)
        except KeyError:
            return {"error": f"Tool '{name}' not found."}
            
        # Security Gate
        # For v0.2, if it's a destructive action (like write_file), block it unless explicit confirmation is bypassed.
        # In a real CLI flow, this is where we'd yield control back to the user for a Yes/No.
        action_desc = f"{name} with args {payload}"
        sec_check = self.security_engine.allow_action(name)
        
        if not sec_check["allowed"]:
            # Here we simulate the dry-run / confirmation required state
            if require_confirmation:
                struct_log(_logger, "warning", event="tool_requires_confirmation", action=action_desc)
                return {
                    "status": "pending_confirmation", 
                    "reason": sec_check["reason"], 
                    "action": action_desc,
                    "payload_to_retry": payload
                }
            else:
                struct_log(_logger, "warning", event="tool_blocked", action=action_desc)
                return {"error": f"Action blocked by SecurityEngine: {sec_check['reason']}"}
        
        # Execute tool
        struct_log(_logger, "info", event="tool_execute", name=name, payload=payload)
        try:
            result = tool.invoke(payload)
            return {"status": "success", "result": result}
        except Exception as e:
            struct_log(_logger, "error", event="tool_error", name=name, error=str(e))
            return {"error": f"Tool execution failed: {str(e)}"}
