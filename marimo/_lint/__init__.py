# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._lint.base import LintError, LintRule, Severity
from marimo._lint.checker import LintChecker
from marimo._lint.formatting import GeneralFormattingRule
from marimo._lint.runtime import (
    MultipleDefinitionsRule,
    CycleDependenciesRule,
    SetupCellDependenciesRule,
)
from marimo._lint.breaking import UnparsableCellsRule
from marimo._ast.parse import NotebookSerialization
from typing import List


def lint_notebook(notebook: NotebookSerialization) -> List[LintError]:
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
    "UnparsableCellsRule",
    "lint_notebook",
]
