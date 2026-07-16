"""Small structured logging helper for COS components.

Provides `struct_log(logger, level, **kwargs)` which logs JSON-encoded
events via the standard logger.
"""
import json
import logging
from typing import Any


def struct_log(logger: logging.Logger, level: str, **kwargs: Any) -> None:
    try:
        payload = json.dumps(kwargs, ensure_ascii=False)
    except Exception:
        # fallback to str representation
        payload = json.dumps({"msg": str(kwargs)})
    if level == "info":
        logger.info(payload)
    elif level == "warning":
        logger.warning(payload)
    elif level == "error":
        logger.error(payload)
    else:
        logger.debug(payload)


def get_logger(name: str = "cos") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
