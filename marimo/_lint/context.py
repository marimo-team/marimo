# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import heapq
import logging  # noqa: TC003
import threading
from typing import TYPE_CHECKING

from marimo._ast.names import SETUP_CELL_NAME

# Note: load_notebook_ir not used - we do manual compilation for per-cell log capture
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._loggers import capture_output
from marimo._schemas.serialization import CellDef, NotebookSerialization
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._lint.rules.base import LintRule
    from marimo._runtime.dataflow import DirectedGraph

# Priority mapping: lower numbers = higher priority
PRIORITY_MAP = {
    Severity.BREAKING: 0,
    Severity.RUNTIME: 1,
    Severity.FORMATTING: 2,
}


class LintContext:
    """Context for lint rule execution with priority queuing and graph caching."""

    def __init__(
        self,
        notebook: NotebookSerialization,
        contents: str = "",
        stderr: str = "",
        stdout: str = "",
        logs: list[logging.LogRecord] | None = None,
    ):
        self.notebook = notebook
        self.contents = contents.splitlines()
        self._diagnostics: list[tuple[int, int, Diagnostic]] = []
        self._graph: DirectedGraph | None = None
        self._graph_lock = threading.Lock()
        self._diagnostics_lock: asyncio.Lock | None = None  # Lazy-initialized
        self._counter = 0  # Monotonic counter for stable sorting
        self._last_retrieved_counter = (
            -1
        )  # Track what was last retrieved for streaming

        self.stderr = stderr
        self.stdout = stdout
        self._log_records = logs or []
        self._logs_by_rule: dict[str, list[logging.LogRecord]] = {}
        self._logs_by_cell_and_rule: dict[
            str, dict[str, list[logging.LogRecord]]
        ] = {}

        self._errors: dict[str, list[tuple[Exception, CellDef]]] = {}

    def _get_diagnostics_lock(self) -> asyncio.Lock:
        """Get the diagnostics lock, creating it if needed."""
        if self._diagnostics_lock is None:
            self._diagnostics_lock = asyncio.Lock()
        return self._diagnostics_lock

    async def add_diagnostic(self, diagnostic: Diagnostic) -> None:
        """Add a diagnostic to the priority queue."""
        priority = 999  # Default low priority
        if diagnostic.severity:
            priority = PRIORITY_MAP.get(diagnostic.severity, priority)

        # Use counter as tiebreaker to avoid comparing Diagnostic objects
        async with self._get_diagnostics_lock():
            heapq.heappush(
                self._diagnostics, (priority, self._counter, diagnostic)
            )
            self._counter += 1

    async def get_diagnostics(self) -> list[Diagnostic]:
        """Get all diagnostics sorted by priority (most severe first)."""
        # Sort by priority and return just the diagnostics
        async with self._get_diagnostics_lock():
            sorted_diagnostics = []
            temp_heap = self._diagnostics.copy()

            while temp_heap:
                _, _, diagnostic = heapq.heappop(temp_heap)
                sorted_diagnostics.append(diagnostic)

            return sorted_diagnostics

    async def get_new_diagnostics(self) -> list[Diagnostic]:
        """Get diagnostics added since last call, sorted by priority."""
        async with self._get_diagnostics_lock():
            # Find new diagnostics since last retrieval
            new_items = [
                (priority, counter, diagnostic)
                for priority, counter, diagnostic in self._diagnostics
                if counter > self._last_retrieved_counter
            ]

            if not new_items:
                return []

            # Sort by priority (and counter for stability)
            new_items.sort()

            # Extract diagnostics and update counter
            new_diagnostics = []
            max_counter = self._last_retrieved_counter

            for _priority, counter, diagnostic in new_items:
                new_diagnostics.append(diagnostic)
                max_counter = max(max_counter, counter)

            # Update the last retrieved counter
            self._last_retrieved_counter = max_counter

            return new_diagnostics

    def _group_initial_logs(self) -> None:
        """Group initial log records by rule code."""
        for record in self._log_records:
            # Check if record has lint_rule metadata
            lint_rule = getattr(record, "lint_rule", None)
            if hasattr(record, "__dict__") and "lint_rule" in record.__dict__:
                lint_rule = record.__dict__["lint_rule"]

            # Default to MF006 (misc) if no specific rule
            rule_code = lint_rule if lint_rule else "MF006"

            if rule_code not in self._logs_by_rule:
                self._logs_by_rule[rule_code] = []
            self._logs_by_rule[rule_code].append(record)

    def _enhance_cell_logs(
        self,
        cell_logs: list[logging.LogRecord],
        cell_id: str,
        cell_lineno: int,
    ) -> None:
        """Enhance log records with cell information and store globally."""
        for record in cell_logs:
            # Add cell information to the log record
            if hasattr(record, "__dict__"):
                record.__dict__["cell_id"] = cell_id
                record.__dict__["cell_lineno"] = cell_lineno

            lint_rule = getattr(record, "lint_rule", None)
            if hasattr(record, "__dict__") and "lint_rule" in record.__dict__:
                lint_rule = record.__dict__["lint_rule"]

            rule_code = lint_rule if lint_rule else "MF006"
            if rule_code not in self._logs_by_rule:
                self._logs_by_rule[rule_code] = []
            self._logs_by_rule[rule_code].append(record)

        self._log_records.extend(cell_logs)

    def get_graph(self) -> DirectedGraph:
        """Get the dependency graph, constructing it once and caching."""
        if self._graph is not None:
            return self._graph

        with self._graph_lock:
            # Double-check pattern for thread safety
            if self._graph is not None:
                return self._graph

            # Group any initial logs
            self._group_initial_logs()

            # Manually compile the graph with per-cell log capture
            from marimo._ast.app import App, InternalApp
            from marimo._ast.cell import CellConfig
            from marimo._ast.cell_manager import CellManager
            from marimo._ast.compiler import ir_cell_factory
            from marimo._schemas.serialization import UnparsableCell

            # Create the app
            app = App(
                **self.notebook.app.options, _filename=self.notebook.filename
            )
            self._graph = app._graph

            # Process each cell individually to capture logs per-cell
            for i, cell in enumerate(self.notebook.cells):
                if isinstance(cell, UnparsableCell):
                    app._unparsable_cell(cell.code, **cell.options)
                    continue

                # Capture logs during this specific cell's compilation
                with capture_output() as (_, _, cell_logs):
                    # Call ir_cell_factory directly with proper exception handling
                    if cell.name == SETUP_CELL_NAME:
                        cell_id = CellId_t(SETUP_CELL_NAME)
                    else:
                        cell_id = app._cell_manager.create_cell_id()
                    filename = self.notebook.filename
                    cell_config = CellConfig.from_dict(cell.options)

                    try:
                        compiled_cell = ir_cell_factory(
                            cell, cell_id=cell_id, filename=filename
                        )
                        compiled_cell._cell.configure(cell_config)
                        # Register the successfully compiled cell
                        app._cell_manager._register_cell(
                            compiled_cell, InternalApp(app)
                        )
                    except SyntaxError as e:
                        # Handle syntax errors like register_ir_cell does
                        app._cell_manager.unparsable = True
                        app._cell_manager.register_cell(
                            cell_id=cell_id,
                            code=cell.code,
                            config=cell_config,
                            name=cell.name,
                            cell=None,
                        )
                        self._errors.setdefault("SyntaxError", []).append(
                            (e, cell)
                        )
                    except Exception as e:
                        self._errors.setdefault("unhandled", []).append(
                            (e, cell)
                        )

                # Enhance logs with cell information and store globally
                simplified_cell_id = f"cell-{i}"
                self._enhance_cell_logs(
                    cell_logs, simplified_cell_id, cell.lineno
                )

            # Initialize the app to register cells in the graph
            cell_manager: CellManager = app._cell_manager
            for cell_id, cell_impl in cell_manager.valid_cells():
                self._graph.register_cell(cell_id, cell_impl._cell)

            return self._graph


class RuleContext:
    """Context for a specific rule execution that wraps LintContext with filename info."""

    def __init__(self, global_context: LintContext, rule: LintRule):
        self.global_context = global_context
        self.rule = rule

    async def add_diagnostic(self, diagnostic: Diagnostic) -> None:
        """Add a diagnostic with context filled in from rule and notebook."""
        # Backfill any None attributes from rule defaults
        if diagnostic.code is None:
            diagnostic.code = self.rule.code
        if diagnostic.name is None:
            diagnostic.name = self.rule.name
        if diagnostic.severity is None:
            diagnostic.severity = self.rule.severity
        if diagnostic.fixable is None:
            diagnostic.fixable = self.rule.fixable

        # Set filename from notebook
        if diagnostic.filename is None:
            diagnostic.filename = self.global_context.notebook.filename

        await self.global_context.add_diagnostic(diagnostic)

    def get_graph(self) -> DirectedGraph:
        """Access to the dependency graph."""
        return self.global_context.get_graph()

    @property
    def contents(self) -> list[str]:
        """Access to file contents being linted."""
        return self.global_context.contents

    @property
    def notebook(self) -> NotebookSerialization:
        """Access to the notebook being linted."""
        return self.global_context.notebook

    @property
    def stdout(self) -> str:
        """Access to the captured stdout."""
        return self.global_context.stdout

    @property
    def stderr(self) -> str:
        """Access to the captured stderr."""
        return self.global_context.stderr

    def get_errors(self, key: str) -> list[tuple[Exception, CellDef]]:
        return self.global_context._errors.get(key, [])

    def get_logs(
        self, rule_code: str | None = None
    ) -> list[logging.LogRecord]:
        """Get log records for a specific rule or all logs if no rule specified."""
        if rule_code is None:
            return self.global_context._log_records

        return self.global_context._logs_by_rule.get(rule_code, [])

    def get_logs_for_cell(
        self, cell_id: str, rule_code: str | None = None
    ) -> list[logging.LogRecord]:
        """Get log records for a specific cell and rule."""
        if cell_id not in self.global_context._logs_by_cell_and_rule:
            return []

        cell_logs = self.global_context._logs_by_cell_and_rule[cell_id]
        if rule_code is None:
            # Return all logs for this cell
            all_logs = []
            for logs in cell_logs.values():
                all_logs.extend(logs)
            return all_logs

        return cell_logs.get(rule_code, [])
