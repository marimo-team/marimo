# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for `marimo check`, the notebook linter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._ast.parse import parse_notebook
from marimo._lint.rule_engine import RuleEngine

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

    from marimo._schemas.serialization import NotebookSerialization


@pytest.fixture(scope="module")
def rule_engine() -> RuleEngine:
    return RuleEngine.create_default()


def test_lint_notebook(
    benchmark: BenchmarkFixture,
    rule_engine: RuleEngine,
    notebook: str,
) -> None:
    """Run every default lint rule over a 50-cell notebook."""
    ir: NotebookSerialization | None = parse_notebook(
        notebook, filepath="notebook.py"
    )
    assert ir is not None

    @benchmark
    def _() -> None:
        rule_engine.check_notebook_sync(ir)
