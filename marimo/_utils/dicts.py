# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeVar

S = TypeVar("S")
T = TypeVar("T")


def remove_none_values(d: dict[S, T]) -> dict[S, T]:
    """Return a copy of the dictionary with all None-valued entries removed."""
    return {k: v for k, v in d.items() if v is not None}
