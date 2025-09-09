# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import NotebookSerialization
from marimo._lint.base import LintError, LintRule


class LintChecker:
    """Orchestrates lint rules and provides checking and fixing functionality."""

    def __init__(self, rules: list[LintRule]):
        self.rules = rules

    def check_notebook(
        self, notebook: NotebookSerialization
    ) -> list[LintError]:
        """Check notebook for all lint rule violations."""
        errors = []

        for rule in self.rules:
            rule_errors = rule.check(notebook)
            errors.extend(rule_errors)

        return errors

    @classmethod
    def create_default(cls) -> LintChecker:
        """Create a LintChecker with all default rules."""
        from marimo._lint.breaking import UnparsableCellsRule
        from marimo._lint.formatting import GeneralFormattingRule
        from marimo._lint.runtime import (
            CycleDependenciesRule,
            MultipleDefinitionsRule,
            SetupCellDependenciesRule,
        )

        rules = [
            GeneralFormattingRule(),
            MultipleDefinitionsRule(),
            CycleDependenciesRule(),
            SetupCellDependenciesRule(),
            UnparsableCellsRule(),
        ]

        return cls(rules)
