"""Example tool plugin implementing a simple echo/increment behavior.

This demonstrates the plugin API: plugin must expose `invoke(payload)`.
"""


class ExamplePlugin:
    def invoke(self, payload: dict) -> dict:
        # Simple deterministic behavior for tests/demos
        msg = payload.get("message", "")
        return {"ok": True, "echo": msg, "len": len(msg)}


# Register instance at import time for convenience
from . import registry
registry.register("example", ExamplePlugin())
