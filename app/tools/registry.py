"""Simple MCP-like plugin registry for tools.

API:
  - register(name: str, plugin: object)
  - get_tool(name: str) -> plugin or raise
  - list_tools() -> list[str]

Plugins are expected to expose an `invoke(payload: dict) -> dict` method.
"""
from typing import Dict, Any

_REGISTRY: Dict[str, Any] = {}


def register(name: str, plugin: Any) -> None:
    _REGISTRY[name] = plugin


def get_tool(name: str) -> Any:
    if name not in _REGISTRY:
        raise KeyError(f"Tool not found: {name}")
    return _REGISTRY[name]


def list_tools() -> list[str]:
    return list(_REGISTRY.keys())


def init_default_tools() -> None:
    from .fs_tools import ReadFileTool, WriteFileTool
    from .macro_tools import SearchAndReplaceTool
    register("read_file", ReadFileTool())
    register("write_file", WriteFileTool())
    register("search_and_replace", SearchAndReplaceTool())

# Initialize automatically
init_default_tools()
