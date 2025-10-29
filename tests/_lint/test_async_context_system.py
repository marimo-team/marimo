# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for the async context-based lint system."""

from marimo._ast.parse import parse_notebook
from marimo._lint.context import LintContext, RuleContext
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rule_engine import RuleEngine
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import MultipleDefinitionsRule, UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from tests._lint.utils import lint_notebook


class MockRule(LintRule):
    """Mock rule for testing."""

    def __init__(
        self, code: str, severity: Severity, diagnostic_count: int = 1
    ):
        # Set class attributes dynamically
        self.code = code
        self.name = f"mock-{code.lower()}"
        self.description = f"Mock rule {code}"
        self.severity = severity
        self.fixable = False

        # Instance attributes
        self.diagnostic_count = diagnostic_count
        self.call_count = 0

    async def check(self, rule_ctx: RuleContext) -> None:
        """Add mock diagnostics to context."""
        self.call_count += 1
        for i in range(self.diagnostic_count):
            diagnostic = Diagnostic(
                message=f"Mock diagnostic {i + 1}",
                cell_id=None,
                line=1,
                column=1,
                code=self.code,
                name=self.name,
                severity=self.severity,
                fixable=self.fixable,
            )
            await rule_ctx.add_diagnostic(diagnostic)


class TestLintContext:
    """Test the LintContext class."""

    def setup_method(self):
        self.notebook = parse_notebook("import marimo\napp = marimo.App()")
        self.ctx = LintContext(self.notebook)

    async def test_add_diagnostic_priority_queue(self):
        """Test that diagnostics are queued by priority."""
        # Add diagnostics in reverse priority order
        formatting_diag = Diagnostic(
            message="formatting",
            cell_id=None,
            line=1,
            column=1,
            code="MF001",
            name="test",
            severity=Severity.FORMATTING,
            fixable=False,
        )
        breaking_diag = Diagnostic(
            message="breaking",
            cell_id=None,
            line=1,
            column=1,
            code="MB001",
            name="test",
            severity=Severity.BREAKING,
            fixable=False,
        )
        runtime_diag = Diagnostic(
            message="runtime",
            cell_id=None,
            line=1,
            column=1,
            code="MR001",
            name="test",
            severity=Severity.RUNTIME,
            fixable=False,
        )

        # Add in non-priority order
        await self.ctx.add_diagnostic(formatting_diag)
        await self.ctx.add_diagnostic(runtime_diag)
        await self.ctx.add_diagnostic(breaking_diag)

        # Get diagnostics - should be sorted by priority
        diagnostics = await self.ctx.get_diagnostics()

        assert len(diagnostics) == 3
        assert diagnostics[0].severity == Severity.BREAKING
        assert diagnostics[1].severity == Severity.RUNTIME
        assert diagnostics[2].severity == Severity.FORMATTING

    async def test_add_diagnostic_stable_order(self):
        """Test that diagnostics with same priority maintain insertion order."""
        # Add multiple diagnostics with same priority
        diag1 = Diagnostic(
            message="first",
            cell_id=None,
            line=1,
            column=1,
            code="MF001",
            name="test1",
            severity=Severity.FORMATTING,
            fixable=False,
        )
        diag2 = Diagnostic(
            message="second",
            cell_id=None,
            line=1,
            column=1,
            code="MF002",
            name="test2",
            severity=Severity.FORMATTING,
            fixable=False,
        )
        diag3 = Diagnostic(
            message="third",
            cell_id=None,
            line=1,
            column=1,
            code="MF003",
            name="test3",
            severity=Severity.FORMATTING,
            fixable=False,
        )

        await self.ctx.add_diagnostic(diag1)
        await self.ctx.add_diagnostic(diag2)
        await self.ctx.add_diagnostic(diag3)

        diagnostics = await self.ctx.get_diagnostics()

        assert len(diagnostics) == 3
        assert diagnostics[0].message == "first"
        assert diagnostics[1].message == "second"
        assert diagnostics[2].message == "third"

    def test_graph_caching(self):
        """Test that the graph is cached and reused."""
        # First call should construct the graph
        graph1 = self.ctx.get_graph()

        # Second call should return the same graph instance
        graph2 = self.ctx.get_graph()

        assert graph1 is graph2

    def test_graph_thread_safety(self):
        """Test that graph construction is thread-safe."""
        import threading
        import time

        graphs = []
        exceptions = []

        def get_graph():
            try:
                # Add small delay to increase chance of race condition
                time.sleep(0.001)
                graph = self.ctx.get_graph()
                graphs.append(graph)
            except Exception as e:
                exceptions.append(e)

        # Create multiple threads trying to get the graph simultaneously
        threads = [threading.Thread(target=get_graph) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All threads should succeed and get the same graph instance
        assert len(exceptions) == 0
        assert len(graphs) == 10
        assert all(graph is graphs[0] for graph in graphs)


class TestAsyncRuleEngine:
    """Test the async RuleEngine functionality."""

    def setup_method(self):
        self.notebook = parse_notebook("import marimo\napp = marimo.App()")

    async def test_async_rule_execution(self):
        """Test that rules are executed asynchronously."""
        # Create mock rules with different severities
        breaking_rule = MockRule(
            "MB001", Severity.BREAKING, diagnostic_count=2
        )
        runtime_rule = MockRule("MR001", Severity.RUNTIME, diagnostic_count=1)
        formatting_rule = MockRule(
            "MF001", Severity.FORMATTING, diagnostic_count=3
        )

        checker = RuleEngine([breaking_rule, runtime_rule, formatting_rule])

        # Execute rules
        diagnostics = await checker.check_notebook(self.notebook)

        # All rules should have been called
        assert breaking_rule.call_count == 1
        assert runtime_rule.call_count == 1
        assert formatting_rule.call_count == 1

        # Should get diagnostics in priority order
        assert len(diagnostics) == 6  # 2 + 1 + 3

        # First two should be breaking
        assert diagnostics[0].severity == Severity.BREAKING
        assert diagnostics[1].severity == Severity.BREAKING

        # Next should be runtime
        assert diagnostics[2].severity == Severity.RUNTIME

        # Last three should be formatting
        assert diagnostics[3].severity == Severity.FORMATTING
        assert diagnostics[4].severity == Severity.FORMATTING
        assert diagnostics[5].severity == Severity.FORMATTING

    def test_sync_wrapper(self):
        """Test the synchronous wrapper."""
        mock_rule = MockRule("MF001", Severity.FORMATTING)
        checker = RuleEngine([mock_rule])

        # Should work synchronously
        diagnostics = checker.check_notebook_sync(self.notebook)

        assert len(diagnostics) == 1
        assert mock_rule.call_count == 1

    def test_rule_priority_execution(self):
        """Test that diagnostics are returned in priority order."""
        # Create rules in non-priority order
        formatting_rule = MockRule("MF001", Severity.FORMATTING)
        breaking_rule = MockRule("MB001", Severity.BREAKING)
        runtime_rule = MockRule("MR001", Severity.RUNTIME)

        checker = RuleEngine([formatting_rule, breaking_rule, runtime_rule])

        # Get diagnostics
        diagnostics = checker.check_notebook_sync(self.notebook)

        # Should get diagnostics in priority order regardless of rule submission order
        assert len(diagnostics) == 3
        assert diagnostics[0].severity == Severity.BREAKING  # MB001
        assert diagnostics[1].severity == Severity.RUNTIME  # MR001
        assert diagnostics[2].severity == Severity.FORMATTING  # MF001


class TestRealRules:
    """Test the real rule implementations with the new context system."""

    async def test_formatting_rule(self):
        """Test GeneralFormattingRule with context."""
        # Create notebook with formatting violations
        code = """import marimo

app = marimo.App()

@app.cell
def __():
    x = 1
    return x,
"""
        notebook = parse_notebook(code)
        ctx = LintContext(notebook)

        rule = GeneralFormattingRule()
        await rule.check(ctx)

        diagnostics = await ctx.get_diagnostics()
        # This should succeed without error
        assert isinstance(diagnostics, list)

    async def test_multiple_definitions_rule(self):
        """Test MultipleDefinitionsRule with context."""
        # Create notebook with multiple definitions
        code = """import marimo
app = marimo.App()

@app.cell
def _():
    x = 1
    return

@app.cell
def _():
    x = 2  # Should trigger multiple definitions
    return
"""
        notebook = parse_notebook(code)
        ctx = LintContext(notebook)

        rule = MultipleDefinitionsRule()
        await rule.check(ctx)

        diagnostics = await ctx.get_diagnostics()
        assert len(diagnostics) > 0
        assert diagnostics[0].severity == Severity.BREAKING
        assert "multiple cells" in diagnostics[0].message

    async def test_unparsable_rule(self):
        """Test UnparsableRule with context."""
        # Create a simple notebook (unparsable cells need special setup)
        notebook = parse_notebook("import marimo\napp = marimo.App()")
        ctx = LintContext(notebook)

        rule = UnparsableRule()
        await rule.check(ctx)

        # Should not find any unparsable cells in valid code
        diagnostics = await ctx.get_diagnostics()
        unparsable_diagnostics = [d for d in diagnostics if d.code == "MB001"]
        assert len(unparsable_diagnostics) == 0


class TestIntegration:
    """Integration tests for the complete system."""

    def test_end_to_end_linting(self):
        """Test complete end-to-end linting process."""
        # Create notebook with multiple types of issues
        code = """import marimo
app = marimo.App()

@app.cell
def _():
    x = 1
    return

@app.cell
def _():
    x = 2  # Multiple definitions
    return
"""

        notebook = parse_notebook(code)
        diagnostics = lint_notebook(notebook, code)

        # Should find diagnostics
        assert len(diagnostics) > 0

        # Should be sorted by priority (breaking first, then runtime, then formatting)
        severities = [d.severity for d in diagnostics]
        severity_values = [s.value for s in severities]

        # Check that breaking comes before runtime, runtime before formatting
        priority_order = {"breaking": 0, "runtime": 1, "formatting": 2}
        for i in range(len(severity_values) - 1):
            current_priority = priority_order.get(severity_values[i], 999)
            next_priority = priority_order.get(severity_values[i + 1], 999)
            assert current_priority <= next_priority

    def test_default_checker_creation(self):
        """Test that default checker includes all expected rules."""
        checker = RuleEngine.create_default()

        # Should include all the standard rules
        rule_codes = {rule.code for rule in checker.rules}
        expected_codes = {
            "MF001",
            "MF002",
            "MF003",
            "MB001",
            "MB002",
            "MB003",
            "MB004",
        }

        assert expected_codes.issubset(rule_codes)
