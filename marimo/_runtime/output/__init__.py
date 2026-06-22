# Copyright 2026 Marimo. All rights reserved.
"""Write to a cell's output area."""

__all__ = [
    "append",
    "clear",
    "clear_console",
    "replace",
    "replace_at_index",
]

from marimo._runtime.output._output import (
    append,
    clear,
    clear_console,
    replace,
    replace_at_index,
)
