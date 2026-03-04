"""Utilities for lint tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic
from marimo._lint.rule_engine import RuleEngine
from marimo._schemas.serialization import NotebookSerializationV1

if TYPE_CHECKING:
    from marimo._config.config import LintConfig


def lint_notebook(
    notebook: NotebookSerializationV1,
    contents: str = "",
    lint_config: LintConfig | None = None,
) -> list[Diagnostic]:
    """Lint a notebook and return all diagnostics found."""
    rule_engine = RuleEngine.create_default(lint_config=lint_config)
    return rule_engine.check_notebook_sync(notebook, contents)
