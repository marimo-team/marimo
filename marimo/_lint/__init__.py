# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import NotebookSerialization
from marimo._lint.checker import LintChecker
from marimo._lint.rules.base import LintError, LintRule, Severity
from marimo._lint.rules.breaking import UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._lint.rules.runtime import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)


def lint_notebook(notebook: NotebookSerialization) -> list[LintError]:
    """Lint a notebook and return all errors found.

    Args:
        notebook: The notebook serialization to lint

    Returns:
        List of lint errors found in the notebook
    """
    checker = LintChecker.create_default()
    return checker.check_notebook(notebook)


__all__ = [
    "LintError",
    "LintRule",
    "Severity",
    "LintChecker",
    "GeneralFormattingRule",
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "lint_notebook",
]
