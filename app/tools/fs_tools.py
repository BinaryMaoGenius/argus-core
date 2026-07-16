import os
from typing import Dict, Any

def _safe_path(path: str) -> str:
    root = os.path.realpath(os.environ.get("ARGUS_WORKSPACE_ROOT", os.getcwd()))
    candidate = os.path.realpath(os.path.abspath(path))
    if os.path.commonpath([root, candidate]) != root:
        raise ValueError("Path must stay inside ARGUS_WORKSPACE_ROOT")
    return candidate

class ReadFileTool:
    name = "read_file"
    description = "Read the contents of a file on the local filesystem"

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get("path")
        if not path:
            return {"error": "Missing path parameter"}
        
        try:
            with open(_safe_path(path), "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"error": str(e)}

class WriteFileTool:
    name = "write_file"
    description = "Write text content to a file on the local filesystem"

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get("path")
        content = payload.get("content")
        
        if not path:
            return {"error": "Missing path parameter"}
        if content is None:
            return {"error": "Missing content parameter"}
            
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "message": f"Successfully wrote to {path}"}
        except Exception as e:
            return {"error": str(e)}

