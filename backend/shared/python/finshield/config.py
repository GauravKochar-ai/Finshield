"""Scoring config and runtime settings.

- ``load_config()`` reads contract/config.json (bundled into the layer at build time).
- ``get_setting(name)`` reads SSM ``/finshield/<stage>/<name>`` (cached), with an env override
  ``FINSHIELD_SETTING_<NAME>`` for tests and local runs.
"""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent


def stage() -> str:
    return os.environ.get("STAGE", "dev")


def region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "ap-south-1"


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    if os.environ.get("FINSHIELD_CONTRACT_DIR"):
        dirs.append(Path(os.environ["FINSHIELD_CONTRACT_DIR"]))
    dirs.append(_HERE / "contract")  # bundled into the layer by `make build`
    for parent in _HERE.parents:  # repo checkout (tests, local runs)
        dirs.append(parent / "contract")
    return dirs


@lru_cache(maxsize=1)
def contract_dir() -> Path:
    for d in _candidate_dirs():
        if (d / "config.json").is_file():
            return d
    raise FileNotFoundError("contract/config.json not found; run `make build` or set FINSHIELD_CONTRACT_DIR")


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with open(contract_dir() / "config.json", encoding="utf-8") as fh:
        return json.load(fh)


def severity_for(score: int) -> str | None:
    """Return CRITICAL/HIGH/MEDIUM, or None when the score is logged-only."""
    t = load_config()["severity_thresholds"]
    for level in ("CRITICAL", "HIGH", "MEDIUM"):
        if score >= t[level]:
            return level
    return None


_ssm_cache: dict[str, tuple[str, float]] = {}


def _ssm_client():
    import boto3

    return boto3.client("ssm", region_name=region())


def get_setting(name: str, default: str | None = None, max_age_s: float = 300) -> str | None:
    """Runtime setting from SSM /finshield/<stage>/<name>; env FINSHIELD_SETTING_<NAME> wins.

    Values are cached per Lambda container for ``max_age_s`` seconds. Pass ``max_age_s=0`` for
    switches that must take effect at once (containment_mode).
    """
    env_key = f"FINSHIELD_SETTING_{name.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]
    cached = _ssm_cache.get(name)
    if cached and time.monotonic() - cached[1] < max_age_s:
        return cached[0]
    path = f"/finshield/{stage()}/{name}"
    try:
        value = _ssm_client().get_parameter(Name=path)["Parameter"]["Value"]
    except Exception as exc:  # ParameterNotFound or no access: fall back to default
        if exc.__class__.__name__ == "ParameterNotFound" or default is not None:
            return default
        raise
    _ssm_cache[name] = (value, time.monotonic())
    return value


def clear_cache() -> None:
    _ssm_cache.clear()
    load_config.cache_clear()
    contract_dir.cache_clear()
