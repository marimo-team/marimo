"""Utilities for lint tests."""

from marimo._lint.diagnostic import Diagnostic
from marimo._lint.rule_engine import RuleEngine
from marimo._schemas.serialization import NotebookSerializationV1


def lint_notebook(
    notebook: NotebookSerializationV1, contents: str = ""
) -> list[Diagnostic]:
    """Lint a notebook and return all diagnostics found."""
    rule_engine = RuleEngine.create_default()
    return rule_engine.check_notebook_sync(notebook, contents)
