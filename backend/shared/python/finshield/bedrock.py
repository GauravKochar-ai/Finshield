"""Bedrock Converse wrapper: temperature 0, Guardrail applied, hard timeout, masked input.

Bedrock only writes words. Callers validate output against contract schemas and check numbers.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import boto3
from botocore.config import Config

from .config import get_setting, region

AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


class BedrockUnavailable(RuntimeError):
    """Raised on timeout, throttling, missing config or any invoke failure. Callers use their fallback."""


def mask_text(text: str) -> str:
    """Last-line defence: strip Aadhaar-like and PAN-like strings from prompt text."""
    return PAN_RE.sub("[PAN]", AADHAAR_RE.sub("[AADHAAR]", text))


def _client(timeout_s: float):
    cfg = Config(read_timeout=timeout_s, connect_timeout=min(2, timeout_s), retries={"max_attempts": 1, "mode": "standard"})
    return boto3.client("bedrock-runtime", region_name=region(), config=cfg)


def converse(system: str, user_text: str, timeout_s: float = 8.0, max_tokens: int = 1200, model_id: str | None = None, client: Any = None) -> dict[str, Any]:
    """Call Converse. Returns {text, stop_reason, guardrail_intervened, latency_ms, usage}."""
    model_id = model_id or get_setting("bedrock_model_id")
    guardrail_id = get_setting("guardrail_id")
    guardrail_version = get_setting("guardrail_version", "DRAFT")
    if not model_id or model_id == "NONE":
        raise BedrockUnavailable("bedrock_model_id not configured")
    if not guardrail_id or guardrail_id == "NONE":
        raise BedrockUnavailable("guardrail_id not configured; refusing to call Bedrock without a Guardrail")
    bc = client or _client(timeout_s)
    started = time.monotonic()
    try:
        resp = bc.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": mask_text(user_text)}]}],
            inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
            guardrailConfig={"guardrailIdentifier": guardrail_id, "guardrailVersion": guardrail_version, "trace": "enabled"},
        )
    except Exception as exc:
        raise BedrockUnavailable(f"{exc.__class__.__name__}: {exc}") from exc
    latency_ms = int((time.monotonic() - started) * 1000)
    parts = resp.get("output", {}).get("message", {}).get("content", [])
    text = "".join(p.get("text", "") for p in parts)
    return {
        "text": text,
        "stop_reason": resp.get("stopReason"),
        "guardrail_intervened": resp.get("stopReason") == "guardrail_intervened",
        "latency_ms": latency_ms,
        "usage": resp.get("usage", {}),
        "model_id": model_id,
    }


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in model output (tolerates ``` fences)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(cleaned[start : end + 1])
