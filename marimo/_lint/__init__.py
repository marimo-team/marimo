# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.linter import FileStatus, Linter
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._lint.rules.base import LintRule
from marimo._utils.files import async_expand_file_patterns

if TYPE_CHECKING:
    from collections.abc import Callable


# Define severity ordering (lower index = higher priority)
SEVERITY_ORDER = {
    Severity.BREAKING: 0,
    Severity.RUNTIME: 1,
    Severity.FORMATTING: 2,
}


def run_check(
    file_patterns: tuple[str, ...],
    pipe: Callable[[str], None] | None = None,
    fix: bool = False,
    unsafe_fixes: bool = False,
    ignore_scripts: bool = False,
    formatter: str = "full",
) -> Linter:
    """Run linting checks on files matching patterns (CLI entry point).

    High-level interface that handles file discovery, parsing, and aggregation.
    Used by the `marimo check` command.

    Args:
        file_patterns: Glob patterns for file discovery
        pipe: Optional function to call for streaming output
        fix: Whether to fix files automatically
        unsafe_fixes: Whether to enable unsafe fixes that may change behavior
        ignore_scripts: Whether to ignore files not recognizable as marimo notebooks
        formatter: Output format for diagnostics ("full" or "json")

    Returns:
        Linter with per-file status and diagnostics
    """
    # Get async generator for files
    files_to_check = async_expand_file_patterns(file_patterns)

    linter = Linter(
        pipe=pipe,
        fix_files=fix,
        unsafe_fixes=unsafe_fixes,
        ignore_scripts=ignore_scripts,
        formatter=formatter,
    )
    linter.run_streaming(files_to_check)
    return linter


def collect_messages(
    file_patterns: str | tuple[str, ...],
    min_severity: Severity = Severity.BREAKING,
) -> tuple[Linter, str]:
    """Run linting checks and collect all messages as a string.

    Simple interface for collecting linting messages without streaming output.
    Used when you need to capture all linting output for error reporting.
    Never performs fixes - only collects messages.

    Args:
        file_patterns: File pattern(s) for file discovery
        min_severity: Minimum severity level to include (defaults to BREAKING)

    Returns:
        Tuple of (Linter with per-file status and diagnostics, collected messages)
    """
    messages = []

    def message_pipe(msg: str) -> None:
        messages.append(msg)

    # Normalize to tuple
    if isinstance(file_patterns, str):
        file_patterns = (file_patterns,)

    # Create filtered rules based on severity
    from marimo._lint.rules import RULE_CODES

    min_severity_level = SEVERITY_ORDER[min_severity]
    filtered_rules = [
        rule()
        for rule in RULE_CODES.values()
        if SEVERITY_ORDER[rule().severity] <= min_severity_level
    ]

    # Create linter with filtered rules
    linter = Linter(
        pipe=message_pipe,
        fix_files=False,
        unsafe_fixes=False,
        rules=filtered_rules,
    )

    files_to_check = async_expand_file_patterns(file_patterns)
    linter.run_streaming(files_to_check)

    return linter, "\n".join(messages)


__all__ = [
    "Diagnostic",
    "LintRule",
    "Severity",
    "EarlyStoppingConfig",
    "RuleEngine",
    "run_check",
    "collect_messages",
    "Linter",
    "FileStatus",
]
