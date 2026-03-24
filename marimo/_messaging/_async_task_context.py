# Copyright 2026 Marimo. All rights reserved.
"""Context variable for propagating cell_id to asyncio tasks.

When an async cell creates tasks via asyncio.create_task(), the cell_id
of the cell that created the task needs to be propagated so that
print_override can route print() output to the correct cell.

This module defines the context variable separately to avoid circular imports.
"""
from __future__ import annotations

import contextvars

# Context variable to propagate cell_id to asyncio tasks created via create_task().
# When an async cell creates tasks, we capture the cell_id so that print_override
# can route print() output to the correct cell even when the asyncio task runs
# after the execution context has been cleared.
_asyncio_task_cell_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_asyncio_task_cell_id", default=None
)
