"""JSON Schema validation against contract/schemas."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from .config import contract_dir

SCHEMA_NAMES = ("event", "alert", "ai_explanation", "evidence_entry", "report")


class SchemaError(ValueError):
    def __init__(self, name: str, errors: list[str]):
        self.name = name
        self.errors = errors
        super().__init__(f"{name} invalid: " + "; ".join(errors))


@lru_cache(maxsize=1)
def _schemas() -> dict[str, dict[str, Any]]:
    out = {}
    for name in SCHEMA_NAMES:
        with open(contract_dir() / "schemas" / f"{name}.schema.json", encoding="utf-8") as fh:
            out[name] = json.load(fh)
    return out


@lru_cache(maxsize=1)
def _registry() -> Registry:
    reg = Registry()
    for schema in _schemas().values():
        reg = reg.with_resource(schema["$id"], Resource.from_contents(schema, default_specification=DRAFT7))
    return reg


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft7Validator:
    if name not in SCHEMA_NAMES:
        raise KeyError(f"unknown schema {name!r}")
    return Draft7Validator(_schemas()[name], registry=_registry())


def errors(name: str, obj: Any) -> list[str]:
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in sorted(_validator(name).iter_errors(obj), key=lambda e: list(e.absolute_path))]


def is_valid(name: str, obj: Any) -> bool:
    return not errors(name, obj)


def validate(name: str, obj: Any) -> Any:
    """Return obj if valid, else raise SchemaError."""
    errs = errors(name, obj)
    if errs:
        raise SchemaError(name, errs)
    return obj
