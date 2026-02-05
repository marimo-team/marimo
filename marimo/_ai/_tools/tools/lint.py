# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rule_engine import RuleEngine
from marimo._types.ids import SessionId


@dataclass
class DiagnosticSummary:
    """Summary of diagnostics by severity."""

    total_issues: int = 0
    breaking_issues: int = 0
    runtime_issues: int = 0
    formatting_issues: int = 0


@dataclass
class LintNotebookArgs:
    """Arguments for linting a notebook."""

    session_id: SessionId


@dataclass
class LintNotebookOutput(SuccessResult):
    """Output from linting a notebook."""

    summary: DiagnosticSummary = field(default_factory=DiagnosticSummary)
    diagnostics: list[Diagnostic] = field(default_factory=list)


class LintNotebook(ToolBase[LintNotebookArgs, LintNotebookOutput]):
    """Lint a marimo notebook to check for issues.

    Uses marimo's internal linting engine to check for:
    - Breaking issues: Problems that prevent the notebook from running
    - Runtime issues: Problems that may cause unexpected behavior
    - Formatting issues: Code style and formatting problems

    Args:
        session_id: The session ID of the notebook to lint.

    Returns:
        A success result containing all diagnostics found and issue counts.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "ALWAYS use this tool after making ANY EDITS, CELLS, OR CHANGES to a marimo notebook to verify you didn't introduce any issues",
            "ALWAYS use this tool when you want to lint a marimo notebook instead of using your own default linting tool",
            "When the user asks to check or validate their notebook",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
        ],
        avoid_if=[
            "You just made changes to fix lint issues - explain what you fixed instead of immediately linting again",
        ],
        additional_info=(
            "This tool provides static analysis only and does not execute code. "
            "Some issues may require running the notebook to fully diagnose."
        ),
    )

    async def handle(self, args: LintNotebookArgs) -> LintNotebookOutput:  # type: ignore[override]
        session = self.context.get_session(args.session_id)
        notebook_ir = session.app_file_manager.app.to_ir()

        rule_engine = RuleEngine.create_default()
        diagnostics = await rule_engine.check_notebook(notebook_ir)

        summary = self._get_diagnostic_summary(diagnostics)

        next_steps = self._build_next_steps(summary)

        return LintNotebookOutput(
            diagnostics=diagnostics,
            summary=summary,
            next_steps=next_steps,
        )

    def _get_diagnostic_summary(
        self, diagnostics: list[Diagnostic]
    ) -> DiagnosticSummary:
        """Get summary of diagnostics by severity."""
        summary = DiagnosticSummary()

        for diagnostic in diagnostics:
            if diagnostic.severity == Severity.BREAKING:
                summary.breaking_issues += 1
            elif diagnostic.severity == Severity.RUNTIME:
                summary.runtime_issues += 1
            elif diagnostic.severity == Severity.FORMATTING:
                summary.formatting_issues += 1

            summary.total_issues += 1

        return summary

    def _build_next_steps(self, summary: DiagnosticSummary) -> list[str]:
        """Build next steps based on the summary of diagnostics."""
        next_steps = []
        if summary.breaking_issues > 0:
            next_steps.append(
                f"Fix {summary.breaking_issues} breaking issue(s) that prevent the notebook from running properly"
            )
        if summary.runtime_issues > 0:
            next_steps.append(
                f"Address {summary.runtime_issues} runtime issue(s) that may cause unexpected behavior"
            )
        if summary.formatting_issues > 0:
            next_steps.append(
                f"Optionally fix {summary.formatting_issues} formatting issue(s) for better code style"
            )
        if summary.total_issues == 0:
            next_steps.append("No issues found - notebook is healthy!")

        return next_steps
