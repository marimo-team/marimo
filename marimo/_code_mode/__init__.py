# Copyright 2026 Marimo. All rights reserved.
"""Code mode: programmatic notebook editing via async context manager.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.

Usage::

    import marimo._code_mode as cm

    async with cm.get_context() as ctx:
        # Create cells (appends at end by default)
        cid = ctx.create_cell("x = 1")
        ctx.create_cell("y = x + 1", after=cid)

        # Update cells by ID or name
        ctx.edit_cell("my_cell", code="z = 42")

        # Delete cells
        ctx.delete_cell("old_cell")

        # Move cells
        ctx.move_cell("my_cell", after="other_cell")

    # Read cells (works outside the context manager too)
    ctx = cm.get_context()
    ctx.cells[0]  # by index
    ctx.cells["my_cell"]  # by name
"""

from __future__ import annotations

import sys
from types import ModuleType

from marimo._code_mode._capabilities import (
    capabilities,
    load_capability,
)
from marimo._code_mode._context import (
    AsyncCodeModeContext,
    CellStatusType,
    NotebookCell,
    StaleCellError,
    get_context,
)

__all__ = [
    "AsyncCodeModeContext",
    "CellStatusType",
    "NotebookCell",
    "StaleCellError",
    "capabilities",
    "get_context",
    "load_capability",
]


# Lets us make `help(cm)` dynamic.
class _CodeModeModule(ModuleType):
    @property
    def __doc__(self) -> str | None:
        doc = self.__dict__.get("__doc__")
        if not isinstance(doc, str):
            return None

        installed = capabilities()
        if not installed:
            return doc

        names = ", ".join(installed)
        return (
            f"{doc}\n\n"
            f"Installed capabilities: {names}\n\n"
            "Run `cm.capabilities()` to list them, then "
            "`cm.load_capability(name)` to load one."
        )

    @__doc__.setter
    def __doc__(self, value: str | None) -> None:
        self.__dict__["__doc__"] = value


sys.modules[__name__].__class__ = _CodeModeModule
