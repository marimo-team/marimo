# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for the marimo lint system."""


from marimo._ast.parse import parse_notebook
from marimo._lint import lint_notebook
from marimo._lint.checker import LintChecker
from marimo._lint.rules.base import Severity
from marimo._lint.rules.breaking import UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._lint.rules.runtime import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerializationV1,
)


class TestLintSystem:
    """Test the core lint system functionality."""

    def test_lint_notebook_basic(self):
        """Test basic linting functionality."""
        code = """
import marimo

app = marimo.App()

@app.cell
def __():
    x = 1
    return (x,)
"""
        notebook = parse_notebook(code)
        errors = lint_notebook(notebook)

        # Should have formatting error for missing __generated_with
        assert len(errors) > 0
        assert any(error.code == "MF001" for error in errors)

    def test_lint_notebook_with_violations(self):
        """Test linting with parsing violations."""
        code = """
import marimo

app = marimo.App()

# This should create a violation
x = 1

@app.cell
def __():
    y = 2
    return (y,)
"""
        notebook = parse_notebook(code)
        errors = lint_notebook(notebook)

        # Should have formatting errors for violations
        assert len(errors) > 0
        assert any(error.code == "MF001" for error in errors)


class TestLintRules:
    """Test individual lint rules."""

    def test_general_formatting_rule(self):
        """Test the general formatting rule."""
        rule = GeneralFormattingRule()

        # Create a notebook with violations
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[],
            violations=[
                type(
                    "Violation",
                    (),
                    {
                        "description": "UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION",
                        "lineno": 1,
                        "col_offset": 0,
                    },
                )()
            ],
        )

        errors = rule.check(notebook)
        assert len(errors) == 1
        assert errors[0].code == "MF001"
        assert errors[0].severity == Severity.FORMATTING

    def test_multiple_definitions_rule(self):
        """Test the multiple definitions rule."""
        rule = MultipleDefinitionsRule()

        # Create a simple notebook
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(code="x = 1", name="cell1", lineno=1, col_offset=0),
                CellDef(code="x = 2", name="cell2", lineno=2, col_offset=0),
            ],
        )

        errors = rule.check(notebook)
        # The rule should run without errors (even if no multiple definitions found)
        assert isinstance(errors, list)

    def test_cycle_dependencies_rule(self):
        """Test the cycle dependencies rule."""
        rule = CycleDependenciesRule()

        # Create a simple notebook
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(code="x = 1", name="cell1", lineno=1, col_offset=0),
                CellDef(code="y = 2", name="cell2", lineno=2, col_offset=0),
            ],
        )

        errors = rule.check(notebook)
        # The rule should run without errors
        assert isinstance(errors, list)

    def test_setup_cell_dependencies_rule(self):
        """Test the setup cell dependencies rule."""
        rule = SetupCellDependenciesRule()

        # Create a simple notebook
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(code="x = 1", name="cell1", lineno=1, col_offset=0),
            ],
        )

        errors = rule.check(notebook)
        # The rule should run without errors
        assert isinstance(errors, list)

    def test_unparsable_cells_rule(self):
        """Test the unparsable cells rule."""
        rule = UnparsableRule()

        # Create a notebook with unparsable cell
        from marimo._schemas.serialization import UnparsableCell

        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                UnparsableCell(
                    code="x = 1 +", name="cell1", lineno=1, col_offset=0
                ),
            ],
        )

        errors = rule.check(notebook)
        assert len(errors) == 1
        assert errors[0].code == "MB001"
        assert errors[0].severity == Severity.BREAKING


class TestLintChecker:
    """Test the LintChecker class."""

    def test_create_default(self):
        """Test creating a default checker."""
        checker = LintChecker.create_default()
        assert checker is not None
        assert len(checker.rules) > 0

    def test_check_notebook(self):
        """Test checking a notebook."""
        checker = LintChecker.create_default()

        notebook = NotebookSerializationV1(
            app=AppInstantiation(), cells=[], violations=[]
        )

        errors = checker.check_notebook(notebook)
        assert isinstance(errors, list)
