# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import heapq
import logging
import threading
from typing import TYPE_CHECKING

from marimo._ast.load import load_notebook_ir
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._loggers import capture_output
from marimo._schemas.serialization import NotebookSerialization

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
        stderr: str = "",
        stdout: str = "",
        logs: list[logging.LogRecord] | None = None,
    ):
        self.notebook = notebook
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

            # Default to MF007 (misc) if no specific rule
            rule_code = lint_rule if lint_rule else "MF007"

            if rule_code not in self._logs_by_rule:
                self._logs_by_rule[rule_code] = []
            self._logs_by_rule[rule_code].append(record)

    def get_graph(self) -> DirectedGraph:
        """Get the dependency graph, constructing it once and caching."""
        if self._graph is not None:
            return self._graph

        with self._graph_lock:
            # Double-check pattern for thread safety
            if self._graph is not None:
                return self._graph


            # Construct the graph
            with capture_output() as (stdout, stderr, logs):
                app = load_notebook_ir(self.notebook)
            self._graph = app._graph

            # Group any initial logs
            self._group_initial_logs()

            # Group new logs as they come in
            for record in logs:
                # Check if record has lint_rule metadata
                lint_rule = getattr(record, "lint_rule", None)
                if hasattr(record, "__dict__") and "lint_rule" in record.__dict__:
                    lint_rule = record.__dict__["lint_rule"]

                # Default to MF007 (misc) if no specific rule
                rule_code = lint_rule if lint_rule else "MF007"

                if rule_code not in self._logs_by_rule:
                    self._logs_by_rule[rule_code] = []
                self._logs_by_rule[rule_code].append(record)

            self._log_records.extend(logs)

            # Initialize the app to register cells in the graph
            for cell_id, cell in app._cell_manager.valid_cells():
                self._graph.register_cell(cell_id, cell._cell)

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

    def get_logs(self, rule_code: str | None = None) -> list[logging.LogRecord]:
        """Get log records for a specific rule or all logs if no rule specified."""
        if rule_code is None:
            return self.global_context._log_records

        return self.global_context._logs_by_rule.get(rule_code, [])

