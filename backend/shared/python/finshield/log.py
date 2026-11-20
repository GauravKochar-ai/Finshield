"""Structured JSON logging: one JSON object per line, with alert_id / event_id when present."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

_logger = logging.getLogger("finshield")
_logger.setLevel(os.environ.get("FINSHIELD_LOG_LEVEL", "INFO"))


def log(message: str, level: str = "INFO", **fields: Any) -> None:
    record = {"level": level, "message": message, "function": os.environ.get("AWS_LAMBDA_FUNCTION_NAME"), **fields}
    _logger.log(getattr(logging, level, logging.INFO), json.dumps({k: v for k, v in record.items() if v is not None}, default=str))
