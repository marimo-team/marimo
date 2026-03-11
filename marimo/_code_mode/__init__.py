# Copyright 2026 Marimo. All rights reserved.
"""Code mode: programmatic access to act on behalf of the user in a running
marimo notebook.

.. warning::

    **Internal, agent-only API.** Not part of marimo's public API.
    No versioning guarantees. May change or be removed without notice.

Start here::

    import marimo._code_mode as cm

    ctx = cm.get_context()

Build edits and apply them::

    cell = cm.NotebookCellData(code="import polars as pl")
    await ctx.apply_edit(cm.NotebookEdit.insert_cells(0, [cell]))

Read existing cells::

    existing = ctx.cells[0]
    updated = existing.replace(config=CellConfig(hide_code=True))
    await ctx.apply_edit(cm.NotebookEdit.replace_cells(0, [updated]))

Explore ``ctx`` to discover other operations. Check the module
imports in ``_context.py`` and ``_edits.py`` to find where types live.
"""

from __future__ import annotations

from marimo._code_mode._context import AsyncCodeModeContext, get_context
from marimo._code_mode._edits import NotebookCellData, NotebookEdit

__all__ = [
    "AsyncCodeModeContext",
    "NotebookCellData",
    "NotebookEdit",
    "get_context",
]
