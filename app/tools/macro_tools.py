import re
import os
from typing import Dict, Any
from ..logging import get_logger, struct_log
from .fs_tools import _safe_path

_logger = get_logger("macro_tools")

class SearchAndReplaceTool:
    """A macro-tool that reads a file, searches for a pattern, replaces it, and saves the file.
    
    This saves the LLM from executing a 3-step loop (read -> logic -> write).
    """
    name = "search_and_replace"
    description = "Searches for a regex pattern in a file and replaces it with the given string, saving the file."

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get("path")
        pattern = payload.get("pattern")
        replacement = payload.get("replacement")
        
        if not path or not pattern or replacement is None:
            return {"error": "Missing required parameters: path, pattern, replacement"}
            
        try:
            safe_path = _safe_path(path)
            with open(safe_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            new_content, count = re.subn(pattern, replacement, content)
            
            if count == 0:
                return {"success": True, "message": "Pattern not found. No changes made."}
                
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            struct_log(_logger, "info", event="macro_replace_success", path=path, replacements=count)
            return {"success": True, "message": f"Successfully made {count} replacements in {path}"}
            
        except Exception as e:
            struct_log(_logger, "error", event="macro_replace_error", path=path, error=str(e))
            return {"error": str(e)}

