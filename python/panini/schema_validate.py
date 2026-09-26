# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Minimal JSON Schema subset validator for PANINI v0.7 contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


class SchemaError(ValueError):
    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path
        self.detail = message


def load_schema(name: str) -> Dict[str, Any]:
    path = SCHEMA_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance: Any, schema: Dict[str, Any], path: str = "$", cache: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    cache = cache if cache is not None else {}
    if "$ref" in schema and len([k for k in schema if k != "$ref"]) == 0:
        schema = _resolve_ref(schema["$ref"], cache)
    elif "$ref" in schema:
        merged = dict(_resolve_ref(schema["$ref"], cache))
        extra = {k: v for k, v in schema.items() if k != "$ref"}
        merged.update(extra)
        schema = merged

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(instance, dict):
            raise SchemaError(path, f"expected object, got {type(instance).__name__}")
        for key in schema.get("required") or []:
            if key not in instance:
                raise SchemaError(path, f"missing required field {key!r}")
        properties = schema.get("properties") or {}
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], f"{path}.{key}", cache)
            elif additional is False:
                raise SchemaError(path, f"unexpected property {key!r}")
            elif isinstance(additional, dict):
                validate(value, additional, f"{path}.{key}", cache)
    elif expected_type == "array":
        if not isinstance(instance, list):
            raise SchemaError(path, f"expected array, got {type(instance).__name__}")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                validate(item, item_schema, f"{path}[{i}]", cache)
    elif expected_type == "string":
        if not isinstance(instance, str):
            raise SchemaError(path, f"expected string, got {type(instance).__name__}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(path, "string shorter than minLength")
    elif expected_type == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            raise SchemaError(path, f"expected number, got {type(instance).__name__}")
    elif expected_type == "boolean":
        if not isinstance(instance, bool):
            raise SchemaError(path, f"expected boolean, got {type(instance).__name__}")
    elif expected_type == "null":
        if instance is not None:
            raise SchemaError(path, "expected null")
    elif isinstance(expected_type, list):
        ok = False
        last = None
        for opt in expected_type:
            try:
                validate(instance, {**schema, "type": opt}, path, cache)
                ok = True
                break
            except SchemaError as exc:
                last = exc
        if not ok:
            raise last or SchemaError(path, "no union member matched")

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(path, f"expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(path, f"invalid enum value {instance!r}")


def _resolve_ref(ref: str, cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    name = ref.rsplit("/", 1)[-1]
    if name not in cache:
        cache[name] = load_schema(name)
    return cache[name]


def validate_named(instance: Any, schema_filename: str) -> None:
    validate(instance, load_schema(schema_filename))
