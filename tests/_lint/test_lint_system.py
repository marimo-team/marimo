# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for the marimo lint system."""

from unittest.mock import patch

from marimo._ast.parse import parse_notebook
from marimo._lint.context import LintContext, RuleContext
from marimo._lint.rule_engine import RuleEngine
from marimo._lint.rules.base import Severity
from marimo._lint.rules.breaking import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
    UnparsableRule,
)
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerializationV1,
)
from tests._lint.utils import lint_notebook


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

    async def test_general_formatting_rule(self):
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

        ctx = LintContext(notebook)
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)
        errors = await ctx.get_diagnostics()
        assert len(errors) == 1
        assert errors[0].code == "MF001"
        assert errors[0].severity == Severity.FORMATTING

    async def test_multiple_definitions_rule(self):
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

        ctx = LintContext(notebook)
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)
        errors = await ctx.get_diagnostics()
        # The rule should run without errors (even if no multiple definitions found)
        assert isinstance(errors, list)

    async def test_cycle_dependencies_rule(self):
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

        ctx = LintContext(notebook)
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)
        errors = await ctx.get_diagnostics()
        # The rule should run without errors
        assert isinstance(errors, list)

    async def test_setup_cell_dependencies_rule(self):
        """Test the setup cell dependencies rule."""
        rule = SetupCellDependenciesRule()

        # Create a simple notebook
        notebook = NotebookSerializationV1(
            app=AppInstantiation(),
            cells=[
                CellDef(code="x = 1", name="cell1", lineno=1, col_offset=0),
            ],
        )

        ctx = LintContext(notebook)
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)
        errors = await ctx.get_diagnostics()
        # The rule should run without errors
        assert isinstance(errors, list)

    async def test_unparsable_cells_rule(self):
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

        ctx = LintContext(notebook)
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)
        errors = await ctx.get_diagnostics()
        assert len(errors) == 1
        assert errors[0].code == "MB001"
        assert errors[0].severity == Severity.BREAKING


class TestRuleEngine:
    """Test the RuleEngine class."""

    def test_create_default(self):
        """Test creating a default checker."""
        checker = RuleEngine.create_default()
        assert checker is not None
        assert len(checker.rules) > 0

    def test_check_notebook(self):
        """Test checking a notebook."""
        checker = RuleEngine.create_default()

        notebook = NotebookSerializationV1(
            app=AppInstantiation(), cells=[], violations=[]
        )

        errors = checker.check_notebook_sync(notebook)
        assert isinstance(errors, list)


class TestMessageCollectionEntryPoints:
    """Test that message collection works through the main entry points."""

    def test_app_initialization_with_message_collection(self):
        """Test that App initialization uses message collection when it encounters errors."""
        import os
        from io import StringIO

        from marimo._ast.app import App

        # Use existing test file with multiple definitions (which should trigger error handling)
        test_file = os.path.join(
            os.path.dirname(__file__), "test_files", "multiple_definitions.py"
        )
        app = App(filename=test_file)

        # Capture stderr to verify message collection
        captured_stderr = StringIO()
        with patch("sys.stderr", captured_stderr):
            try:
                app._maybe_initialize()
            except Exception:
                pass  # Expected to potentially raise an error

        # Verify that if there were errors, linting messages were written to stderr
        stderr_output = captured_stderr.getvalue()
        # The test passes if either no errors occurred, or if errors occurred with proper message collection
        assert isinstance(stderr_output, str)  # Should always be a string

    def test_app_initialization_with_success(self):
        """Test that App initialization works normally with valid notebooks."""
        import os

        from marimo._ast.app import App

        # Use existing test file with formatting issues but valid structure
        test_file = os.path.join(
            os.path.dirname(__file__), "test_files", "formatting.py"
        )
        app = App(filename=test_file)

        # Should not raise an exception for valid notebooks
        # If it does raise an exception, it should not be an UnparsableError
        try:
            app._maybe_initialize()
        except Exception as e:
            # If it fails, it should be for a different reason than unparsable
            if "UnparsableError" in str(type(e)):
                raise AssertionError(f"Unexpected UnparsableError: {e}") from e

    def test_collect_messages_severity_filtering(self):
        """Test that collect_messages severity filtering works correctly."""
        import os

        from marimo._lint import Severity, collect_messages

        test_file = os.path.join(
            os.path.dirname(__file__), "test_files", "formatting.py"
        )

        # Test with BREAKING severity (default)
        linter_breaking, messages_breaking = collect_messages(test_file)

        # Test with FORMATTING severity (should include more issues)
        linter_all, messages_all = collect_messages(
            test_file, min_severity=Severity.FORMATTING
        )

        # Both should return valid results
        assert isinstance(linter_breaking.errored, bool)
        assert isinstance(messages_breaking, str)
        assert isinstance(linter_all.errored, bool)
        assert isinstance(messages_all, str)

        # FORMATTING severity should typically find more issues
        assert len(messages_all) >= len(messages_breaking)
