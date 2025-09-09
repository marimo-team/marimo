# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.parse import NotebookSerialization
from marimo._lint.rules import RULE_CODES


if TYPE_CHECKING:
    from marimo._lint.rules.base import LintError, LintRule


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
        # TODO: Filter rules based on user configuration if needed
        rules = [rule() for rule in RULE_CODES.values()]
        return cls(rules)
