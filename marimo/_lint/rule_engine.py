# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from marimo._lint.context import LintContext, RuleContext
from marimo._lint.diagnostic import Severity
from marimo._lint.rules import RULE_CODES
from marimo._schemas.serialization import NotebookSerialization

if TYPE_CHECKING:
    import logging
    from collections.abc import AsyncIterator

    from marimo._lint.diagnostic import Diagnostic
    from marimo._lint.rules.base import LintRule


class EarlyStoppingConfig:
    """Configuration for early stopping behavior."""

    def __init__(
        self,
        stop_on_breaking: bool = False,
        stop_on_runtime: bool = False,
        max_diagnostics: Optional[int] = None,
        stop_on_first_of_severity: Optional[Severity] = None,
    ):
        self.stop_on_breaking = stop_on_breaking
        self.stop_on_runtime = stop_on_runtime
        self.max_diagnostics = max_diagnostics
        self.stop_on_first_of_severity = stop_on_first_of_severity

    def should_stop(self, diagnostic: Diagnostic, total_count: int) -> bool:
        """Check if we should stop processing based on this diagnostic."""
        if self.max_diagnostics and total_count >= self.max_diagnostics:
            return True

        if (
            self.stop_on_first_of_severity
            and diagnostic.severity == self.stop_on_first_of_severity
        ):
            return True

        if self.stop_on_breaking and diagnostic.severity == Severity.BREAKING:
            return True

        if self.stop_on_runtime and diagnostic.severity == Severity.RUNTIME:
            return True

        return False


class RuleEngine:
    """Orchestrates lint rules and provides checking functionality for a single notebook."""

    def __init__(
        self,
        rules: list[LintRule],
        early_stopping: Optional[EarlyStoppingConfig] = None,
    ):
        self.rules = rules
        self.early_stopping = early_stopping or EarlyStoppingConfig()

    async def check_notebook_streaming(
        self,
        notebook: NotebookSerialization,
        contents: str = "",
        stdout: str = "",
        stderr: str = "",
        logs: list[logging.LogRecord] | None = None,
    ) -> AsyncIterator[Diagnostic]:
        """Check notebook and yield diagnostics as they become available."""
        ctx = LintContext(notebook, contents, stdout, stderr, logs)

        # Create tasks for all rules with their completion tracking
        pending_tasks = {
            asyncio.create_task(rule.check(RuleContext(ctx, rule))): rule
            for rule in self.rules
        }

        diagnostic_count = 0

        # Process rules as they complete
        while pending_tasks:
            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            # Update pending tasks
            for task in done:
                del pending_tasks[task]

            # Get any new diagnostics and yield them in priority order
            new_diagnostics = await ctx.get_new_diagnostics()
            for diagnostic in new_diagnostics:
                diagnostic_count += 1
                yield diagnostic

                # Check for early stopping
                if self.early_stopping.should_stop(
                    diagnostic, diagnostic_count
                ):
                    # Cancel remaining tasks
                    for task in pending_tasks.keys():
                        task.cancel()

                    # Wait for cancellations to complete
                    await asyncio.gather(
                        *pending_tasks.keys(), return_exceptions=True
                    )
                    return

    async def check_notebook(
        self,
        notebook: NotebookSerialization,
        contents: str = "",
        stdout: str = "",
        stderr: str = "",
        logs: list[logging.LogRecord] | None = None,
    ) -> list[Diagnostic]:
        """Check notebook for all lint rule violations using async execution."""
        diagnostics = []
        async for diagnostic in self.check_notebook_streaming(
            notebook, contents, stdout, stderr, logs
        ):
            diagnostics.append(diagnostic)
        return diagnostics

    def check_notebook_sync(
        self,
        notebook: NotebookSerialization,
        stdout: str = "",
        stderr: str = "",
    ) -> list[Diagnostic]:
        """Synchronous wrapper for check_notebook for backward compatibility."""
        return asyncio.run(self.check_notebook(notebook, stdout, stderr))

    @classmethod
    def create_default(
        cls, early_stopping: Optional[EarlyStoppingConfig] = None
    ) -> RuleEngine:
        """Create a RuleEngine with all default rules."""
        # TODO: Filter rules based on user configuration if needed
        rules = [rule() for rule in RULE_CODES.values()]
        return cls(rules, early_stopping)
