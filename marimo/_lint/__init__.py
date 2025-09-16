# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.linter import FileStatus, Linter
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._lint.rules.base import LintRule
from marimo._utils.files import expand_file_patterns

if TYPE_CHECKING:
    from collections.abc import Callable


def run_check(
    file_patterns: tuple[str, ...],
    pipe: Callable[[str], None] | None = None,
    fix: bool = False,
) -> Linter:
    """Run linting checks on files matching patterns (CLI entry point).

    High-level interface that handles file discovery, parsing, and aggregation.
    Used by the `marimo check` command.

    Args:
        file_patterns: Glob patterns for file discovery
        pipe: Optional function to call for streaming output
        fix: Whether to fix files automatically

    Returns:
        Linter with per-file status and diagnostics
    """
    # Expand patterns to actual files
    files_to_check = expand_file_patterns(file_patterns)

    linter = Linter(pipe=pipe, fix_files=fix)
    linter.run_streaming(files_to_check)
    return linter


__all__ = [
    "Diagnostic",
    "LintRule",
    "Severity",
    "EarlyStoppingConfig",
    "RuleEngine",
    "run_check",
    "Linter",
    "FileStatus",
]
