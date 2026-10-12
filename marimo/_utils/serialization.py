# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from enum import Enum
from typing import Any


def _normalize_nested_enums(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (list, tuple)):
        return [_normalize_nested_enums(item) for item in value]
    if isinstance(value, dict):
        return {
            _normalize_nested_enums(key): _normalize_nested_enums(item)
            for key, item in value.items()
        }
    return value


def serialize_sample_value(value: Any) -> str | int | float:
    """Convert a sampled value to a wire-safe primitive.

    Args:
        value (Any): Sampled value. Enums, including nested enums, use names.
    """
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(_normalize_nested_enums(value), default=str)
        except (RecursionError, TypeError, ValueError):
            return str(value)
    return str(value)
