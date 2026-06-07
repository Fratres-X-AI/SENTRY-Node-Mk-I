"""JSON Schema validation helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - optional at runtime
    jsonschema = None  # type: ignore[assignment]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=8)
def load_schema(name: str) -> dict[str, Any]:
    path = repo_root() / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance: dict[str, Any], schema_name: str) -> None:
    if jsonschema is None:
        raise RuntimeError("jsonschema is required for validation; pip install sentry[dev]")
    jsonschema.validate(instance=instance, schema=load_schema(schema_name))
