"""Utilities for lint tests."""

from marimo._lint.rule_engine import RuleEngine


def lint_notebook(notebook):
    """Lint a notebook and return all diagnostics found."""
    rule_engine = RuleEngine.create_default()
    return rule_engine.check_notebook_sync(notebook)
