# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def format_repr(obj: object, items: Mapping[str, object]) -> str:
    """Format a repr string."""
    kvs = [f"{k}={v}" for k, v in items.items()]
    return f"{obj.__class__.__name__}({', '.join(kvs)})"
