# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List

from marimo._lint.base import LintError, LintRule, Severity
from marimo._ast.parse import NotebookSerialization


class LintChecker:
    """Orchestrates lint rules and provides checking and fixing functionality."""

    def __init__(self, rules: List[LintRule]):
        self.rules = rules

    def check_notebook(
        self, notebook: NotebookSerialization
    ) -> List[LintError]:
        """Check notebook for all lint rule violations."""
        errors = []

        for rule in self.rules:
            rule_errors = rule.check(notebook)
            errors.extend(rule_errors)

        return errors

    @classmethod
    def create_default(cls) -> LintChecker:
        """Create a LintChecker with all default rules."""
        from marimo._lint.formatting import GeneralFormattingRule
        from marimo._lint.runtime import (
            MultipleDefinitionsRule,
            CycleDependenciesRule,
            SetupCellDependenciesRule,
        )
        from marimo._lint.breaking import UnparsableCellsRule

        rules = [
            GeneralFormattingRule(),
            MultipleDefinitionsRule(),
            CycleDependenciesRule(),
            SetupCellDependenciesRule(),
            UnparsableCellsRule(),
        ]

        return cls(rules)
