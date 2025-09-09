# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import NotebookSerialization
from marimo._lint.checker import EarlyStoppingConfig, LintChecker
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._lint.rules.runtime import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)


def lint_notebook(notebook: NotebookSerialization) -> list[Diagnostic]:
    """Lint a notebook and return all diagnostics found.

    Args:
        notebook: The notebook serialization to lint

    Returns:
        List of diagnostics found in the notebook
    """
    checker = LintChecker.create_default()
    return checker.check_notebook_sync(notebook)


__all__ = [
    "Diagnostic",
    "LintRule",
    "Severity",
    "LintChecker",
    "EarlyStoppingConfig",
    "GeneralFormattingRule",
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "lint_notebook",
]
