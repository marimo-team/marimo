# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._lint.validate_graph import (
    check_for_cycles,
    check_for_invalid_root,
    check_for_multiple_definitions,
)
from marimo._lint.visitors import VariableLineVisitor
from marimo._types.ids import CellId_t
from marimo._utils.cell_matching import match_cell_ids_by_similarity

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._schemas.serialization import CellDef


@dataclass
class _ErrorInfo:
    cell_id: CellId_t
    line: int
    column: int


class GraphRule(LintRule):
    """Base class for graph-based lint rules that analyze the dependency graph.

    This class provides the foundation for runtime lint rules that need to analyze
    the cell dependency graph to detect issues like cycles, multiple definitions,
    and setup cell violations. These rules ensure marimo's core constraints are
    maintained for reproducible, executable notebooks.

    The dependency graph represents how cells depend on each other through variable
    definitions and references. marimo uses this graph to determine execution order
    and enforce constraints that make notebooks reliable and shareable.

    See Also:
        - https://docs.marimo.io/guides/understanding_errors/ (Understanding errors)
        - https://docs.marimo.io/guides/editor_features/understanding_dataflow/ (Dataflow)
    """

    def _get_cell_from_id(
        self, cell_id: CellId_t, ctx: RuleContext
    ) -> CellDef | None:
        """Get the corresponding CellDef from notebook serialization for a given cell_id."""
        # For setup cells, use the special setup cell name
        if cell_id == CellId_t("setup"):
            for cell in ctx.notebook.cells:
                if cell.name == CellId_t("setup"):
                    return cell
            return None

        # Use cell matching to map graph cell IDs to notebook cells
        graph = ctx.get_graph()

        # Build code mappings for cell matching using position numbers
        graph_codes = {
            cid: cell.code
            for cid, cell in graph.cells.items()
            if cid != CellId_t("setup")
        }
        notebook_codes = {
            CellId_t(str(i)): cell.code
            for i, cell in enumerate(ctx.notebook.cells)
            if cell.name != CellId_t("setup")
        }

        # Match cell IDs using the existing cell matching system
        cell_mapping = match_cell_ids_by_similarity(
            graph_codes, notebook_codes
        )

        # Find the notebook cell that matches this graph cell_id
        if cell_id in cell_mapping:
            notebook_position = cell_mapping[cell_id]
            # Get the cell at the matched position
            non_setup_cells = [
                cell
                for cell in ctx.notebook.cells
                if cell.name != CellId_t("setup")
            ]
            position = int(notebook_position)
            if 0 <= position < len(non_setup_cells):
                return non_setup_cells[position]

        return None

    def _get_variable_line_info(
        self, cell_id: CellId_t, variable_name: str, ctx: RuleContext
    ) -> tuple[int, int]:
        """Get line and column info for a specific variable within a cell."""
        target_cell = self._get_cell_from_id(cell_id, ctx)

        if target_cell:
            # Parse the cell code to find the variable definition
            tree = ast_parse(target_cell.code)
            visitor = VariableLineVisitor(variable_name)
            visitor.visit(tree)
            if visitor.line_number:
                return (
                    target_cell.lineno + visitor.line_number - 1,
                    target_cell.col_offset + visitor.column_number,
                )
            # Fallback to cell line info
            return target_cell.lineno, target_cell.col_offset + 1

        # Fallback to (0, 0) to indicate unknown line/column
        return 0, 0

    async def check(self, ctx: RuleContext) -> None:
        """Perform graph-based validation using the provided context."""
        # Get the graph from context (cached)
        graph = ctx.get_graph()

        # Call the specific validation method
        await self._validate_graph(graph, ctx)

    @abstractmethod
    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        """Abstract method to validate the graph and add diagnostics to context.

        Args:
            graph: The dependency graph to validate
            ctx: The lint context to add diagnostics to
        """
        pass


class MultipleDefinitionsRule(GraphRule):
    """MB002: Multiple cells define the same variable.

    marimo requires that each variable be defined in only one cell. This constraint
    ensures that notebooks are reproducible, executable as scripts, and shareable
    as web apps with better performance than streamlit.

    When a variable is defined in multiple cells, marimo cannot determine which
    definition to use, leading to unpredictable behavior and hidden bugs.

    ## What it does

    Analyzes the dependency graph to detect variables that are defined in more
    than one cell, which violates marimo's fundamental constraint for reactive execution.

    ## Why is this bad?

    Multiple definitions prevent marimo from:
    - Determining the correct execution order
    - Creating a reliable dependency graph
    - Running notebooks as scripts
    - Providing consistent reactive updates

    This is a breaking error because it makes the notebook non-executable.

    ## Examples

    **Problematic:**
    ```python
    # Cell 1
    x = 1

    # Cell 2
    x = 2  # Error: x defined in multiple cells
    ```

    **Solution:**
    ```python
    # Cell 1
    x = 1

    # Cell 2
    y = 2  # Use different variable name
    ```

    ## References

    - [Multiple Definitions Guide](https://docs.marimo.io/guides/understanding_errors/multiple_definitions/)
    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MB002"
    name = "multiple-definitions"
    description = "Multiple cells define the same variable"
    severity = Severity.BREAKING
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        """Validate the graph for multiple definitions."""
        validation_errors = check_for_multiple_definitions(graph)

        names: dict[str, list[_ErrorInfo]] = {}
        for cell_id, error_list in validation_errors.items():
            for error in error_list:
                # Get specific line info for the variable definition
                line, column = self._get_variable_line_info(
                    cell_id, error.name, ctx
                )
                names.setdefault(error.name, []).append(
                    _ErrorInfo(cell_id=cell_id, line=line, column=column)
                )

        for name in names:
            lines = [info.line for info in names[name]]
            columns = [info.column for info in names[name]]
            cell_ids = [info.cell_id for info in names[name]]

            diagnostic = Diagnostic(
                message=f"Variable '{name}' is defined in multiple cells",
                cell_id=cell_ids,
                line=lines,
                column=columns,
                code=self.code,
                name=self.name,
                severity=self.severity,
                fixable=self.fixable,
                fix=(
                    "Variables must be unique across cells. Alternatively, "
                    f"they can be private with an underscore prefix (i.e. `_{name}`.)"
                ),
            )

            await ctx.add_diagnostic(diagnostic)


class CycleDependenciesRule(GraphRule):
    """MB003: Cells have circular dependencies.

    marimo prevents circular dependencies between cells to ensure a well-defined
    execution order. If cell A declares variable 'a' and reads variable 'b', then
    cell B cannot declare 'b' and read 'a' without creating a cycle.

    Cycles make notebooks non-reproducible and prevent marimo from determining
    the correct execution order, leading to undefined behavior.

    ## What it does

    Analyzes the dependency graph to detect circular references between cells,
    where cells depend on each other in a way that creates an impossible
    execution order.

    ## Why is this bad?

    Circular dependencies prevent marimo from:
    - Determining a valid execution order
    - Running notebooks reproducibly
    - Executing notebooks as scripts
    - Providing reliable reactive updates

    This is a breaking error because it makes the notebook non-executable.

    ## Examples

    **Problematic:**
    ```python
    # Cell 1
    a = b + 1  # Reads b

    # Cell 2
    b = a + 1  # Reads a -> Cycle!
    ```

    **Solution:**
    ```python
    # Cell 1
    a = 1

    # Cell 2
    b = a + 1  # Unidirectional dependency
    ```

    ## References

    - [Cycles Guide](https://docs.marimo.io/guides/understanding_errors/cycles/)
    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MB003"
    name = "cycle-dependencies"
    description = "Cells have circular dependencies"
    severity = Severity.BREAKING
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        """Validate the graph for circular dependencies."""
        validation_errors = check_for_cycles(graph)

        seen = set()
        for cell_id, error_list in validation_errors.items():
            for error in error_list:
                if error.edges_with_vars in seen:
                    continue
                seen.add(error.edges_with_vars)

                cells = []
                lines = []
                columns = []
                for cell_id, variables, _ in error.edges_with_vars:
                    # Get cell from notebook serialization
                    for v in variables:
                        line, column = self._get_variable_line_info(
                            cell_id, v, ctx
                        )
                        cells.append(cell_id)
                        lines.append(line)
                        columns.append(column)

                diagnostic = Diagnostic(
                    message="Cell is part of a circular dependency",
                    cell_id=cells,
                    line=lines,
                    column=columns,
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    fixable=self.fixable,
                )

                await ctx.add_diagnostic(diagnostic)


class SetupCellDependenciesRule(GraphRule):
    """MB004: Setup cell cannot have dependencies.

    The setup cell in marimo is special - it runs first and can define variables
    that are available to all other cells. However, the setup cell itself cannot
    depend on variables defined in other cells, as this would create a dependency
    cycle and violate marimo's execution model.

    The setup cell is designed for imports, configuration, and other initialization
    code that should run before any other cells execute.

    ## What it does

    Validates that the setup cell (if present) does not depend on variables
    defined in other cells, ensuring proper execution order.

    ## Why is this bad?

    Setup cell dependencies break marimo's execution model because:
    - The setup cell must run first to initialize the notebook
    - Dependencies on other cells would create impossible execution order
    - It violates the setup cell's purpose as initialization code

    This is a breaking error because it makes the notebook non-executable.

    ## Examples

    **Problematic:**
    ```python
    # Setup cell
    y = x + 1  # Error: setup depends on other cells

    # Cell 1
    x = 1
    ```

    **Solution:**
    ```python
    # Setup cell
    y = 1  # Setup defines its own variables

    # Cell 1
    x = y + 1  # Other cells can use setup variables
    ```

    ## References

    - [Setup References Guide](https://docs.marimo.io/guides/understanding_errors/setup/)
    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MB004"
    name = "setup-cell-dependencies"
    description = "Setup cell cannot have dependencies"
    severity = Severity.BREAKING
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        """Validate the graph for setup cell dependency violations."""
        validation_errors = check_for_invalid_root(graph)

        for cell_id, error_list in validation_errors.items():
            for _ in error_list:
                # Get cell from notebook serialization
                cell = self._get_cell_from_id(cell_id, ctx)
                line, column = (
                    (cell.lineno, cell.col_offset + 1) if cell else (0, 0)
                )

                diagnostic = Diagnostic(
                    message="Setup cell cannot have dependencies",
                    cell_id=[cell_id],
                    line=line,
                    column=column,
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    fixable=self.fixable,
                )

                await ctx.add_diagnostic(diagnostic)
