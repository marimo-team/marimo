# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._ast.compiler import compile_cell
from marimo._ast.names import SETUP_CELL_NAME
from marimo._ast.parse import ast_parse
from marimo._ast.toplevel import HINT_ORDER_DEPENDENT, TopLevelExtraction
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import UnsafeFixRule
from marimo._schemas.serialization import NotebookSerialization
from marimo._types.ids import CellId_t

_HINT_ORDER_DEPENDENT_PREFIX = HINT_ORDER_DEPENDENT.split("{}")[0]

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.toplevel import TopLevelStatus
    from marimo._lint.context import RuleContext
    from marimo._schemas.serialization import CellDef


class ReusableDefinitionOrderRule(UnsafeFixRule):
    """MR003: Invalid ordering of potentially reusable definitions.

    This rule detects cells that could be reusable definitions (i.e., decorated
    with ``@app.function`` or ``@app.class_definition``) but which _cannot_ be
    safely serialized as reusable due to the ordering of marimo cells.


    ## What it does

    marimo serializes reusable definitions in notebook order. Like all python
    scripts, a reusable function cannot refer to a variable that has _not yet
    been defined_. While ordering in marimo normally doesn't matter, for reuse
    as a module or script, dependent top level definitions must be ordered
    correctly.

    This rule flags and fixes function or class definitions that would normally
    be saved as "reusable", but cannot due to cell ordering.

    ## Why is this bad?

    When a reusable definition depends on another reusable definition declared
    later in the notebook:

    - the definition cannot be serialized as reusable
    - imports from other notebooks or Python modules may fail


    ## Examples

    **Problematic:**
    ```python
    @app.function
    def uses_offset(x: int = offset()) -> int:
        # This will run in marimo, but will cause an error if run as a script!
        # `offset` is not defined!
        return x + 1


    @app.function
    def offset() -> int:
        return 1
    ```

    **Problematic:**
    ```python
    @app.cell
    def _():
        # This could be reusable if it was defined after `decorate`.
        class Wrapped:
            @decorate
            def value(self) -> int:
                return 1


    @app.function
    def decorate(fn):
        return fn
    ```

    ## Solution

    Move the referenced reusable definitions earlier in the notebook so they
    appear before the reusable definition that depends on them.

    ```python
    @app.function
    def offset() -> int:
        return 1


    @app.function
    def uses_offset(x: int = offset()) -> int:
        return x + 1
    ```

    ## Unsafe fix

    This rule can be fixed with:

    ```bash
    marimo check --fix --unsafe-fixes my_notebook.py
    ```

    The unsafe fix reorders the provider cells earlier in the notebook. This
    is marked unsafe because changing cell order changes the document
    structure, even when the resulting notebook is still valid.


    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [setup](https://docs.marimo.io/guides/understanding_errors/setup/)
    - [Reusing functions](https://docs.marimo.io/guides/reusing_functions/)
    """

    code = "MR003"
    name = "reusable-definition-order"
    description = (
        "Reusable definitions depending on later reusable definitions"
    )
    severity = Severity.RUNTIME
    fixable = "unsafe"

    async def check(self, ctx: RuleContext) -> None:
        extraction, notebook_indices = self._extract_notebook(ctx.notebook)

        for status, notebook_index in zip(
            extraction.statuses, notebook_indices
        ):
            if not (
                status.hint
                and status.hint.startswith(_HINT_ORDER_DEPENDENT_PREFIX)
            ):
                continue

            notebook_cell = ctx.notebook.cells[notebook_index]
            definition_name = self._get_definition_name(status)
            line, column = self._get_definition_line_info(
                notebook_cell, definition_name
            )
            refs = ", ".join(
                f"`{name}`" for name in sorted(status.dependencies)
            )
            diagnostic = Diagnostic(
                message=(
                    f"Reusable definition '{definition_name}' depends on reusable "
                    f"definition(s) declared later in the notebook: {refs}"
                ),
                cell_id=[CellId_t(str(notebook_index))],
                line=line,
                column=column,
                fixable="unsafe",
                fix=(
                    "Move the referenced reusable definition(s) earlier in the "
                    f"notebook, before `{definition_name}`."
                ),
            )
            await ctx.add_diagnostic(diagnostic)

    def apply_unsafe_fix(
        self, notebook: NotebookSerialization, diagnostics: list[Diagnostic]
    ) -> NotebookSerialization:
        del diagnostics

        cells = list(notebook.cells)

        for _ in range(len(cells) * len(cells)):
            extraction, notebook_indices = self._extract_notebook(
                replace(notebook, cells=cells)
            )
            provider_indices = {
                status.name: notebook_index
                for status, notebook_index in zip(
                    extraction.statuses, notebook_indices
                )
                if status.is_toplevel
            }

            moved = False
            for status, notebook_index in zip(
                extraction.statuses, notebook_indices
            ):
                if not (
                    status.hint
                    and status.hint.startswith(_HINT_ORDER_DEPENDENT_PREFIX)
                ):
                    continue

                later_provider_indices = sorted(
                    provider_indices[name]
                    for name in status.dependencies
                    if name in provider_indices
                    and provider_indices[name] > notebook_index
                )
                if not later_provider_indices:
                    continue

                cells = self._move_cells_before(
                    cells,
                    source_indices=later_provider_indices,
                    target_index=notebook_index,
                )
                moved = True
                break

            if not moved:
                break

        return replace(notebook, cells=cells)

    @staticmethod
    def _move_cells_before(
        cells: list[CellDef], source_indices: list[int], target_index: int
    ) -> list[CellDef]:
        to_move = set(source_indices)
        moved_cells = [cell for i, cell in enumerate(cells) if i in to_move]
        remaining_cells = [
            cell for i, cell in enumerate(cells) if i not in to_move
        ]
        return (
            remaining_cells[:target_index]
            + moved_cells
            + remaining_cells[target_index:]
        )

    @staticmethod
    def _extract_notebook(
        notebook: NotebookSerialization,
    ) -> tuple[TopLevelExtraction, list[int]]:
        from marimo._ast.cell import CellConfig

        compiled_cells: list[CellImpl] = []
        notebook_indices: list[int] = []
        setup_cell: CellImpl | None = None
        filename = (
            notebook.filename
            if notebook.filename and Path(notebook.filename).exists()
            else None
        )

        for index, cell in enumerate(notebook.cells):
            try:
                compiled = compile_cell(
                    cell.code,
                    cell_id=CellId_t(str(index)),
                    filename=filename,
                ).configure(CellConfig.from_dict(cell.options))
            except SyntaxError:
                continue

            if cell.name == SETUP_CELL_NAME:
                setup_cell = compiled
            else:
                compiled_cells.append(compiled)
                notebook_indices.append(index)

        return TopLevelExtraction.from_cells(
            compiled_cells, setup=setup_cell
        ), notebook_indices

    @staticmethod
    def _get_definition_line_info(
        cell: CellDef, definition_name: str
    ) -> tuple[int, int]:
        try:
            tree = ast_parse(cell.code)
        except SyntaxError:
            return cell.lineno, cell.col_offset + 1

        for node in tree.body:
            if (
                isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and node.name == definition_name
            ):
                return (
                    cell.lineno + node.lineno - 1,
                    cell.col_offset + node.col_offset + 1,
                )

        return cell.lineno, cell.col_offset + 1

    @staticmethod
    def _get_definition_name(status: TopLevelStatus) -> str:
        if status.defs:
            return sorted(status.defs)[0]
        return status.name
