# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from marimo._ast.load import load_notebook_ir
from marimo._ast.parse import NotebookSerialization, ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._lint.validate_graph import (
    check_for_cycles,
    check_for_invalid_root,
    check_for_multiple_definitions,
)
from marimo._lint.visitors import VariableLineVisitor
from marimo._utils.cell_matching import match_cell_ids_by_similarity

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph


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

    def __init__(
        self,
        code: str,
        name: str,
        description: str,
        severity: Severity,
        fixable: bool = False,
    ):
        super().__init__(code, name, description, severity, fixable)

    def _get_graph(self, notebook: NotebookSerialization) -> DirectedGraph:
        """Get the dependency graph from the notebook."""
        app = load_notebook_ir(notebook)
        graph = app._graph

        # Initialize the app to register cells in the graph
        # Add cells to graph
        for cell_id, cell in app._cell_manager.valid_cells():
            graph.register_cell(cell_id, cell._cell)
        # app._maybe_initialize()
        return app._graph

    def _get_cell_from_id(self, cell_id: str, notebook: NotebookSerialization) -> DirectedGraph | None:
        """Get the corresponding CellDef from notebook serialization for a given cell_id."""
        # For setup cells, use the special setup cell name
        if cell_id == "setup":
            for cell in notebook.cells:
                if cell.name == "setup":
                    return cell
            return None

        # Use cell matching to map graph cell IDs to notebook cells
        graph = self._get_graph(notebook)

        # Build code mappings for cell matching using position numbers
        graph_codes = {
            cid: cell.code
            for cid, cell in graph.cells.items()
            if cid != "setup"
        }
        notebook_codes = {
            str(i): cell.code
            for i, cell in enumerate(notebook.cells)
            if cell.name != "setup"
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
                cell for cell in notebook.cells if cell.name != "setup"
            ]
            position = int(notebook_position)
            if 0 <= position < len(non_setup_cells):
                return non_setup_cells[position]

        return None

    def _get_variable_line_info(
        self, cell_id: str, variable_name: str, notebook: NotebookSerialization
    ) -> tuple[int, int]:
        """Get line and column info for a specific variable within a cell."""
        target_cell = self._get_cell_from_id(cell_id, notebook)

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

    def check(self, notebook: NotebookSerialization) -> list[Diagnostic]:
        """Perform graph-based validation.

        Args:
            notebook: The notebook to check

        Returns:
            List of Diagnostic objects
        """
        # Get the graph using the base class method
        graph = self._get_graph(notebook)

        # Call the specific validation method
        return self._validate_graph(graph, notebook)

    @abstractmethod
    def _validate_graph(
        self, graph, notebook: NotebookSerialization
    ) -> list[Diagnostic]:
        """Abstract method to validate the graph and return Diagnostic objects.

        Args:
            graph: The dependency graph to validate
            notebook: The notebook serialization for cell information

        Returns:
            List of Diagnostic objects
        """
        pass


class MultipleDefinitionsRule(GraphRule):
    """MR001: Multiple cells define the same variable.

    marimo requires that each variable be defined in only one cell. This constraint
    ensures that notebooks are reproducible, executable as scripts, and shareable
    as web apps with better performance than streamlit.

    When a variable is defined in multiple cells, marimo cannot determine which
    definition to use, leading to unpredictable behavior and hidden bugs.

    See Also:
        - https://docs.marimo.io/guides/understanding_errors/multiple_definitions/
        - https://docs.marimo.io/guides/understanding_errors/ (Understanding errors)

    Examples:
        Violation:
            Cell 1: x = 1
            Cell 2: x = 2  # Error: x defined in multiple cells

        Solution:
            Cell 1: x = 1
            Cell 2: y = 2  # Use different variable name
    """

    def __init__(self):
        super().__init__(
            code="MR001",
            name="multiple-definitions",
            description="Multiple cells define the same variable",
            severity=Severity.RUNTIME,
            fixable=False,
        )

    def _validate_graph(
        self, graph, notebook: NotebookSerialization
    ) -> list[Diagnostic]:
        """Validate the graph for multiple definitions."""
        diagnostics = []
        validation_errors = check_for_multiple_definitions(graph)

        names = {}
        for cell_id, error_list in validation_errors.items():
            for error in error_list:
                # Get specific line info for the variable definition
                line, column = self._get_variable_line_info(
                    cell_id, error.name, notebook
                )
                names.setdefault(error.name, []).append(
                    {"cell_id": cell_id, "line": line, "column": column}
                )

        for name in names:
            lines = [info["line"] for info in names[name]]
            columns = [info["column"] for info in names[name]]
            cell_id = [info["cell_id"] for info in names[name]]
            diagnostics.append(
                Diagnostic(
                    code=self.code,
                    name=self.name,
                    message=f"Variable '{name}' is defined in multiple cells",
                    severity=self.severity,
                    cell_id=cell_id,
                    line=lines,
                    column=columns,
                    fixable=self.fixable,
                    fix=("Variables must be unique across cells. Alternatively, "
                    f"they can be private with an underscore prefix (i.e. `_{name}`.)")
                )
            )

        return diagnostics


class CycleDependenciesRule(GraphRule):
    """MR002: Cells have circular dependencies.

    marimo prevents circular dependencies between cells to ensure a well-defined
    execution order. If cell A declares variable 'a' and reads variable 'b', then
    cell B cannot declare 'b' and read 'a' without creating a cycle.

    Cycles make notebooks non-reproducible and prevent marimo from determining
    the correct execution order, leading to undefined behavior.

    See Also:
        - https://docs.marimo.io/guides/understanding_errors/cycles/
        - https://docs.marimo.io/guides/understanding_errors/ (Understanding errors)

    Examples:
        Violation:
            Cell 1: a = b + 1  # Reads b
            Cell 2: b = a + 1  # Reads a -> Cycle!

        Solution:
            Cell 1: a = 1
            Cell 2: b = a + 1  # Unidirectional dependency
    """

    def __init__(self):
        super().__init__(
            code="MR002",
            name="cycle-dependencies",
            description="Cells have circular dependencies",
            severity=Severity.RUNTIME,
            fixable=False,
        )

    def _validate_graph(
        self, graph, notebook: NotebookSerialization
    ) -> list[Diagnostic]:
        """Validate the graph for circular dependencies."""
        diagnostics = []
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
                            cell_id, v, notebook
                        )
                        cells.append(cell_id)
                        lines.append(line)
                        columns.append(column)

                diagnostics.append(
                    Diagnostic(
                        code=self.code,
                        name=self.name,
                        message="Cell is part of a circular dependency",
                        severity=self.severity,
                        cell_id=cells,
                        line=lines,
                        column=columns,
                        fixable=self.fixable,
                    )
                )

        return diagnostics


class SetupCellDependenciesRule(GraphRule):
    """MR003: Setup cell cannot have dependencies.

    The setup cell in marimo is special - it runs first and can define variables
    that are available to all other cells. However, the setup cell itself cannot
    depend on variables defined in other cells, as this would create a dependency
    cycle and violate marimo's execution model.

    The setup cell is designed for imports, configuration, and other initialization
    code that should run before any other cells execute.

    See Also:
        - https://docs.marimo.io/guides/understanding_errors/setup/
        - https://docs.marimo.io/guides/understanding_errors/ (Understanding errors)

    Examples:
        Violation:
            Setup cell: y = x + 1  # Error: setup depends on other cells
            Cell 1: x = 1

        Solution:
            Setup cell: y = 1  # Setup defines its own variables
            Cell 1: x = y + 1  # Other cells can use setup variables
    """

    def __init__(self):
        super().__init__(
            code="MR003",
            name="setup-cell-dependencies",
            description="Setup cell cannot have dependencies",
            severity=Severity.RUNTIME,
            fixable=False,
        )

    def _validate_graph(
        self, graph, notebook: NotebookSerialization
    ) -> list[Diagnostic]:
        """Validate the graph for setup cell dependency violations."""
        diagnostics = []
        validation_errors = check_for_invalid_root(graph)

        for cell_id, error_list in validation_errors.items():
            for _ in error_list:
                # Get cell from notebook serialization
                cell = self._get_cell_from_id(cell_id, notebook)
                line, column = (
                    (cell.lineno, cell.col_offset + 1) if cell else (0, 0)
                )

                diagnostics.append(
                    Diagnostic(
                        code=self.code,
                        name=self.name,
                        message="Setup cell cannot have dependencies",
                        severity=self.severity,
                        cell_id=cell_id,
                        line=line,
                        column=column,
                        fixable=self.fixable,
                    )
                )

        return diagnostics
