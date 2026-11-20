"""HTTP API helpers: {data, error} envelope, Cognito groups, path/body parsing. Used by api, decision, release, ask,
tamper_demo, simulator and test_runner."""
from __future__ import annotations

import json
from typing import Any

from .schema import _schemas

ALL = "all"


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def is_http(event: Any) -> bool:
    return isinstance(event, dict) and "routeKey" in event and "requestContext" in event


def claims(event) -> dict:
    return ((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims", {}) or {}


def groups(event) -> set[str]:
    g = claims(event).get("cognito:groups") or []
    if isinstance(g, str):
        g = g.strip("[]").replace(",", " ").split()
    return set(g)


def caller(event) -> str:
    c = claims(event)
    return c.get("email") or c.get("cognito:username") or c.get("username") or c.get("sub") or "unknown"


def require(event, allowed) -> None:
    """allowed: list of group names, or ["all"] for any signed-in user."""
    if ALL in allowed:
        if not claims(event):
            raise HttpError(401, "UNAUTHORIZED", "sign-in required")
        return
    if not groups(event) & set(allowed):
        raise HttpError(403, "FORBIDDEN", f"needs one of the groups {sorted(allowed)}")


def body(event) -> dict:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode()
    try:
        out = json.loads(raw)
    except ValueError:
        raise HttpError(400, "BAD_REQUEST", "body is not valid JSON")
    if not isinstance(out, dict):
        raise HttpError(400, "BAD_REQUEST", "body must be a JSON object")
    return out


def path_id(event) -> str:
    pid = (event.get("pathParameters") or {}).get("id")
    if not pid:
        raise HttpError(400, "BAD_REQUEST", "missing id in path")
    return pid


def respond(status: int, data: Any = None, code: str | None = None, message: str | None = None) -> dict:
    out = {"data": data, "error": None if code is None else {"code": code, "message": message}}
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(out, default=str)}


def run(event, fn) -> dict:
    """Call fn() and wrap the result or the HttpError in the envelope."""
    try:
        return respond(200, fn())
    except HttpError as e:
        return respond(e.status, code=e.code, message=e.message)


def public_alert(row: dict | None) -> dict | None:
    """Only the fields in alert.schema.json (drops internal fields such as approval_token)."""
    if row is None:
        return None
    keys = _schemas()["alert"]["properties"]
    return {k: v for k, v in row.items() if k in keys}
