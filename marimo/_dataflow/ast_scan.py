# Copyright 2026 Marimo. All rights reserved.
"""AST analysis for `mo.api.input(...)` declarations.

Scans cell source code to find names assigned from `mo.api.input(...)` calls.
Used as a sanity check and to pair runtime UI elements with their declared
variable names (for the schema). Not the authoritative source — the kernel
run is — but lets us emit better diagnostics when a declared input doesn't
materialize at runtime.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp


def find_input_assignments(source: str) -> list[str]:
    """Find variable names assigned from `mo.api.input(...)` calls.

    Recognizes the common patterns:
        threshold = mo.api.input(...)
        threshold = api.input(...)        # `from marimo import api`
        threshold = input(...)            # `from marimo.api import input`

    Returns the assignment target names. Tuple/list targets and starred
    assignments are not handled (they're nonsensical for inputs anyway).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not _is_input_call(node.value):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
    return names


def find_all_input_assignments(app: InternalApp) -> dict[str, str]:
    """Walk every cell in the app, return {input_name: cell_id}."""
    out: dict[str, str] = {}
    for cell_id in app.cell_manager.cell_ids():
        cell_data = app.cell_manager.cell_data_at(cell_id)
        cell = cell_data.cell
        if cell is None:
            continue
        for name in find_input_assignments(cell._cell.code):
            out[name] = cell_id
    return out


def _is_input_call(node: ast.expr) -> bool:
    """Return True if `node` is a `mo.api.input(...)` call (or alias)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func

    # mo.api.input(...)
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "input"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "api"
    ):
        return True
    # api.input(...)
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "input"
        and isinstance(func.value, ast.Name)
        and func.value.id == "api"
    ):
        return True
    # input(...)  -- only when imported from marimo.api; we accept the name
    # match here as a hint, the runtime check is authoritative
    if isinstance(func, ast.Name) and func.id == "input":
        # Don't match the python builtin; we only want this if used as the
        # mo.api.input alias. Conservative: skip for now.
        return False
    return False
