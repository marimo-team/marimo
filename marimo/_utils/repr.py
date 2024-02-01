# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any


def format_repr(obj: Any, items: dict[str, Any]) -> str:
    """Format a repr string."""
    kvs = [f"{k}={v}" for k, v in items.items()]
    return f"{obj.__class__.__name__}({', '.join(kvs)})"
