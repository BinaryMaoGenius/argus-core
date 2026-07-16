from typing import Any, Dict, List
import subprocess
import os
import shlex
from shutil import which
import time
from ..logging import get_logger, struct_log


_logger = get_logger("execution")


class ExecutionEngine:
    """ExecutionEngine that enforces SecurityEngine before actions and
    executes real shell commands when allowed.

    Warning: commands are executed on the host. `SecurityEngine` MUST block
    destructive commands. Tests should mock `subprocess.run` to avoid side effects.
    """

    def __init__(self, security, memory_kernel=None):
        self.security = security
        self.memory = memory_kernel


    def _run_shell(self, cmd: str, timeout: int = 30) -> Dict[str, Any]:
        # Prefer running through shell=False when possible. If cmd is a string,
        # shell composition is rejected by SecurityEngine; execute without a shell.
        try:
            # If command looks like a single executable, prefer list form
            if isinstance(cmd, str) and " " not in cmd and which(cmd):
                struct_log(_logger, "info", event="run_shell_exec", cmd=cmd)
                completed = subprocess.run([cmd], capture_output=True, text=True, timeout=timeout)
            else:
                struct_log(_logger, "info", event="run_shell_argv", cmd=cmd)
                argv = ["cmd.exe", "/d", "/s", "/c", cmd] if os.name == "nt" else shlex.split(cmd)
                completed = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=timeout)
            return {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "timeout"}
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    async def _execute_single_action(self, action: Dict[str, Any], confirmed: bool = False) -> Dict[str, Any]:
        aid = action.get("id")
        atype = action.get("type", "noop")
        content = action.get("cmd") or action.get("payload") or ""

        if atype == "shell":
            policy = self.security.allow_action(str(content), kind="shell")
            if not policy.get("allowed", False):
                struct_log(_logger, "warning", event="action_blocked", id=aid, action=content, reason=policy.get("reason"))
                return {"id": aid, "status": "blocked", "reason": policy.get("reason")}

        elif atype == "tool":
            policy = self.security.allow_action(str(action.get("tool") or ""), confirmed=confirmed)
            if not policy.get("allowed", False):
                struct_log(_logger, "warning", event="action_blocked", id=aid, action=action.get("tool"), reason=policy.get("reason"))
                return {"id": aid, "status": "blocked", "reason": policy.get("reason")}

        if atype == "noop":
            return {"id": aid, "status": "ok", "output": None}
        elif atype == "shell":
            struct_log(_logger, "info", event="execute_shell", id=aid, cmd=content)
            # Run in a thread to avoid blocking the async event loop
            import asyncio
            out = await asyncio.to_thread(self._run_shell, str(content))
            struct_log(_logger, "info", event="shell_done", id=aid, returncode=out.get("returncode"))
            return {"id": aid, "status": "executed", "output": out}
        elif atype == "tool":
            try:
                from app.tools import registry
                tool_name = action.get("tool")
                if tool_name and hasattr(registry, "get_tool"):
                    tool = registry.get_tool(tool_name)
                    # Tools might be sync, run in thread
                    import asyncio
                    tool_out = await asyncio.to_thread(tool.invoke, action.get("payload", {}))
                    return {"id": aid, "status": "tool_executed", "output": tool_out}
                else:
                    struct_log(_logger, "warning", event="no_tool", id=aid, tool=tool_name)
                    return {"id": aid, "status": "no_tool", "output": None}
            except Exception as e:
                struct_log(_logger, "error", event="tool_error", id=aid, error=str(e))
                return {"id": aid, "status": "tool_error", "error": str(e)}
        else:
            return {"id": aid, "status": "unknown_action", "output": None}

    async def execute_plan(self, plan: List[Dict[str, Any]], confirmed: bool = False) -> List[Dict[str, Any]]:
        import asyncio
        results: List[Dict[str, Any]] = []
        
        # Group actions by async_group
        groups: Dict[int, List[Dict[str, Any]]] = {}
        for action in plan:
            grp = action.get("async_group", 0)
            groups.setdefault(grp, []).append(action)
            
        # Execute groups sequentially, but tasks within a group concurrently
        for grp in sorted(groups.keys()):
            actions_in_group = groups[grp]
            tasks_total = len(actions_in_group)
            struct_log(_logger, "info", event="execute_async_group", group=grp, tasks=tasks_total)

            if tasks_total == 0:
                continue

            tasks = [self._execute_single_action(action, confirmed=confirmed) for action in actions_in_group]
            group_results = await asyncio.gather(*tasks)
            results.extend(group_results)

            if self.memory is not None:
                # Determine failures (status invalid/absent => failure)
                def _is_success(res: Dict[str, Any]) -> bool:
                    return res.get("status") in {"ok", "executed", "tool_executed"}

                tasks_failed = sum(1 for r in group_results if not _is_success(r))

                first_error = None
                if tasks_failed > 0:
                    # Deterministic: first failing result in the same order as group_results
                    first_result = next(r for r in group_results if not _is_success(r))
                    # error: key "error" takes precedence, else key "reason", else null
                    err_val = str(first_result["error"]) if "error" in first_result else (
                        str(first_result["reason"]) if "reason" in first_result else None
                    )
                    first_error = {
                        "error": err_val,
                        "reason": first_result.get("reason", None),
                        "action_id": first_result.get("id", None),
                    }

                # Ensure required keys always present
                if first_error is None:
                    first_error = None

                item = {
                    "async_group": int(grp),
                    "tasks_total": int(tasks_total),
                    "tasks_failed": int(tasks_failed),
                    "ts": time.time() if 'time' in globals() else 0,
                    "first_error": first_error,
                }
                self.memory.push(item=item, tag="execution_result")

        return results






