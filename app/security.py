"""Centralised policy checks for effectful actions."""
from __future__ import annotations

import re
import shlex
from typing import Dict, Any
from .logging import get_logger, struct_log

_logger = get_logger("security")


class SecurityEngine:
    """Conservative policy gate for the non-sandboxed local executor."""

    def __init__(self, policy: Dict[str, Any] | None = None):
        self.policy = policy or {}

    def allow_action(self, action: str, kind: str = "generic", confirmed: bool = False) -> Dict[str, Any]:
        normalized = (action or "").strip()
        lower = normalized.lower()

        if lower in {"write_file", "search_and_replace"} and not confirmed:
            reason = f"{normalized} requires explicit human confirmation"
            struct_log(_logger, "warning", event="action_blocked", action=action, reason=reason)
            return {"allowed": False, "reason": reason}

        if any(token in normalized for token in (";", "&", "|", ">", "<", "`", "\n", "\r", "$(", "%")):
            reason = "Shell composition and redirection are not allowed"
            struct_log(_logger, "warning", event="action_blocked", action=action, reason=reason)
            return {"allowed": False, "reason": reason}

        destructive = r"(?i)(^|[\\/\s])(rm|rmdir|del|erase|drop|shutdown|format|curl|wget|scp|invoke-webrequest)(\s|$)"
        if re.search(destructive, normalized):
            reason = "Destructive actions require explicit approval"
            struct_log(_logger, "warning", event="action_blocked", action=action, reason=reason)
            return {"allowed": False, "reason": reason}

        try:
            command = shlex.split(normalized, posix=False)[0].lower() if normalized else ""
        except ValueError:
            command = ""
        command = command.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        allowed_commands = {"echo", "dir", "type", "where", "whoami"}
        if kind == "shell" and command and command not in allowed_commands:
            reason = f"Command '{command}' is not on the shell allowlist"
            struct_log(_logger, "warning", event="action_blocked", action=action, reason=reason)
            return {"allowed": False, "reason": reason}

        struct_log(_logger, "info", event="action_allowed", action=action)
        return {"allowed": True, "reason": "OK"}



