# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

"""Write to a cell's output area."""

__all__ = [
    "append",
    "clear",
    "replace",
    "replace_at_index",
]

from marimo._runtime.output._output import (
    append,
    clear,
    replace,
    replace_at_index,
)
