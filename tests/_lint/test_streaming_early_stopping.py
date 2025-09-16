# Copyright 2025 Marimo. All rights reserved.
"""Unit tests for streaming diagnostics and early stopping functionality."""

import asyncio

from marimo._ast.parse import parse_notebook
from marimo._lint.context import LintContext
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._lint.rules.base import LintRule


def create_diagnostic(
    code: str,
    cell_id: str,
    message: str,
    severity: Severity,
    fixable: bool = False,
) -> Diagnostic:
    """Helper to create diagnostic with correct parameter order."""
    return Diagnostic(
        message=message,
        cell_id=cell_id,
        line=1,
        column=1,
        code=code,
        severity=severity,
        fixable=fixable,
    )


class SlowRule(LintRule):
    """Mock rule that takes time to complete."""

    def __init__(
        self,
        code: str,
        severity: Severity,
        delay: float = 0.1,
        diagnostic_count: int = 1,
    ):
        # Set class attributes dynamically
        self.code = code
        self.name = f"slow-{code.lower()}"
        self.description = f"Slow rule {code}"
        self.severity = severity
        self.fixable = False

        # Instance attributes
        self.delay = delay
        self.diagnostic_count = diagnostic_count
        self.started = False
        self.completed = False
        self.cancelled = False

    async def check(self, ctx: LintContext) -> None:
        """Add diagnostics after delay."""
        self.started = True
        try:
            await asyncio.sleep(self.delay)
            for i in range(self.diagnostic_count):
                diagnostic = Diagnostic(
                    code=self.code,
                    name=self.name,
                    message=f"Slow diagnostic {i + 1}",
                    severity=self.severity,
                    cell_id=None,
                    line=1,
                    column=1,
                    fixable=self.fixable,
                )
                await ctx.add_diagnostic(diagnostic)
            self.completed = True
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class TestLintContextStreaming:
    """Test LintContext streaming functionality."""

    def setup_method(self):
        self.notebook = parse_notebook("import marimo\napp = marimo.App()")
        self.ctx = LintContext(self.notebook)

    async def test_get_new_diagnostics_empty(self):
        """Test get_new_diagnostics when no diagnostics added."""
        new_diagnostics = await self.ctx.get_new_diagnostics()
        assert len(new_diagnostics) == 0

    async def test_get_new_diagnostics_incremental(self):
        """Test get_new_diagnostics returns only new diagnostics."""
        # Add first batch
        diag1 = Diagnostic(
            message="first",
            cell_id="test1",
            line=1,
            column=1,
            code="MF001",
            severity=Severity.FORMATTING,
            fixable=False,
        )
        diag2 = Diagnostic(
            message="second",
            cell_id="test2",
            line=1,
            column=1,
            code="MR001",
            severity=Severity.RUNTIME,
            fixable=False,
        )

        await self.ctx.add_diagnostic(diag1)
        await self.ctx.add_diagnostic(diag2)

        # Get first batch
        new_diagnostics = await self.ctx.get_new_diagnostics()
        assert len(new_diagnostics) == 2
        assert (
            new_diagnostics[0].severity == Severity.RUNTIME
        )  # Higher priority first
        assert new_diagnostics[1].severity == Severity.FORMATTING

        # Add second batch
        diag3 = create_diagnostic("MB001", "test3", "third", Severity.BREAKING)
        await self.ctx.add_diagnostic(diag3)

        # Get only new diagnostics
        new_diagnostics = await self.ctx.get_new_diagnostics()
        assert len(new_diagnostics) == 1
        assert new_diagnostics[0].severity == Severity.BREAKING

        # Calling again should return empty
        new_diagnostics = await self.ctx.get_new_diagnostics()
        assert len(new_diagnostics) == 0

    async def test_get_all_diagnostics_still_works(self):
        """Test that get_diagnostics still returns all diagnostics."""
        diag1 = create_diagnostic(
            "MF001", "test1", "first", Severity.FORMATTING
        )
        diag2 = create_diagnostic("MR001", "test2", "second", Severity.RUNTIME)

        await self.ctx.add_diagnostic(diag1)
        await self.ctx.add_diagnostic(diag2)

        # Get new diagnostics
        await self.ctx.get_new_diagnostics()

        # get_diagnostics should still return all
        all_diagnostics = await self.ctx.get_diagnostics()
        assert len(all_diagnostics) == 2


class TestEarlyStoppingConfig:
    """Test EarlyStoppingConfig functionality."""

    def test_no_early_stopping(self):
        """Test default config doesn't stop."""
        config = EarlyStoppingConfig()

        breaking_diag = create_diagnostic(
            "MB001", "test", "breaking", Severity.BREAKING
        )
        runtime_diag = create_diagnostic(
            "MR001", "test", "runtime", Severity.RUNTIME
        )

        assert not config.should_stop(breaking_diag, 1)
        assert not config.should_stop(runtime_diag, 1)

    def test_stop_on_breaking(self):
        """Test stopping on breaking severity."""
        config = EarlyStoppingConfig(stop_on_breaking=True)

        breaking_diag = create_diagnostic(
            "MB001", "test", "breaking", Severity.BREAKING
        )
        runtime_diag = create_diagnostic(
            "MR001", "test", "runtime", Severity.RUNTIME
        )

        assert config.should_stop(breaking_diag, 1)
        assert not config.should_stop(runtime_diag, 1)

    def test_stop_on_runtime(self):
        """Test stopping on runtime severity."""
        config = EarlyStoppingConfig(stop_on_runtime=True)

        runtime_diag = create_diagnostic(
            "MR001", "test", "runtime", Severity.RUNTIME
        )
        formatting_diag = create_diagnostic(
            "MF001", "test", "formatting", Severity.FORMATTING
        )

        assert config.should_stop(runtime_diag, 1)
        assert not config.should_stop(formatting_diag, 1)

    def test_max_diagnostics(self):
        """Test stopping based on max diagnostic count."""
        config = EarlyStoppingConfig(max_diagnostics=2)

        diag = Diagnostic(
            "MF001",
            "test",
            "formatting",
            Severity.FORMATTING,
            None,
            1,
            1,
            False,
        )

        assert not config.should_stop(diag, 1)
        assert config.should_stop(diag, 2)
        assert config.should_stop(diag, 3)

    def test_stop_on_first_of_severity(self):
        """Test stopping on first occurrence of specific severity."""
        config = EarlyStoppingConfig(
            stop_on_first_of_severity=Severity.RUNTIME
        )

        runtime_diag = create_diagnostic(
            "MR001", "test", "runtime", Severity.RUNTIME
        )
        breaking_diag = create_diagnostic(
            "MB001", "test", "breaking", Severity.BREAKING
        )
        formatting_diag = create_diagnostic(
            "MF001", "test", "formatting", Severity.FORMATTING
        )

        assert config.should_stop(runtime_diag, 1)
        assert not config.should_stop(breaking_diag, 1)
        assert not config.should_stop(formatting_diag, 1)


class TestStreamingRuleEngine:
    """Test streaming functionality of RuleEngine."""

    def setup_method(self):
        self.notebook = parse_notebook("import marimo\napp = marimo.App()")

    async def test_streaming_basic(self):
        """Test basic streaming functionality."""
        # Create rules with different completion times
        fast_rule = SlowRule("MR001", Severity.RUNTIME, delay=0.01)
        slow_rule = SlowRule("MF001", Severity.FORMATTING, delay=0.05)

        checker = RuleEngine([fast_rule, slow_rule])

        # Collect diagnostics as they stream
        diagnostics = []
        async for diagnostic in checker.check_notebook_streaming(
            self.notebook
        ):
            diagnostics.append(diagnostic)

        # Should get diagnostics as rules complete
        assert len(diagnostics) == 2

        # Fast rule should complete first, but diagnostics are ordered by priority
        # So we should get runtime before formatting
        assert diagnostics[0].severity == Severity.RUNTIME
        assert diagnostics[1].severity == Severity.FORMATTING

        # Both rules should have completed
        assert fast_rule.completed
        assert slow_rule.completed

    async def test_early_stopping_on_breaking(self):
        """Test early stopping cancels remaining tasks."""
        # Create rules with different severities and delays
        fast_breaking = SlowRule("MB001", Severity.BREAKING, delay=0.01)
        slow_formatting = SlowRule(
            "MF001", Severity.FORMATTING, delay=0.1
        )  # Takes longer

        config = EarlyStoppingConfig(stop_on_breaking=True)
        checker = RuleEngine(
            [fast_breaking, slow_formatting], early_stopping=config
        )

        # Collect diagnostics
        diagnostics = []
        async for diagnostic in checker.check_notebook_streaming(
            self.notebook
        ):
            diagnostics.append(diagnostic)

        # Should only get one diagnostic (breaking)
        assert len(diagnostics) == 1
        assert diagnostics[0].severity == Severity.BREAKING

        # Fast rule should complete, slow rule should be cancelled
        assert fast_breaking.completed
        assert slow_formatting.cancelled

    async def test_early_stopping_max_diagnostics(self):
        """Test early stopping based on max diagnostic count."""
        # Create rule that produces multiple diagnostics
        multi_rule = SlowRule(
            "MF001", Severity.FORMATTING, delay=0.01, diagnostic_count=3
        )
        slow_rule = SlowRule("MR001", Severity.RUNTIME, delay=0.1)

        config = EarlyStoppingConfig(max_diagnostics=2)
        checker = RuleEngine([multi_rule, slow_rule], early_stopping=config)

        diagnostics = []
        async for diagnostic in checker.check_notebook_streaming(
            self.notebook
        ):
            diagnostics.append(diagnostic)

        # Should stop after 2 diagnostics
        assert len(diagnostics) == 2

        # Slow rule should be cancelled
        assert slow_rule.cancelled

    def test_backward_compatibility(self):
        """Test that non-streaming methods still work."""
        fast_rule = SlowRule("MR001", Severity.RUNTIME, delay=0.01)
        slow_rule = SlowRule("MF001", Severity.FORMATTING, delay=0.02)

        checker = RuleEngine([fast_rule, slow_rule])

        # Non-streaming method should still work
        diagnostics = checker.check_notebook_sync(self.notebook)

        assert len(diagnostics) == 2
        assert fast_rule.completed
        assert slow_rule.completed


class TestRealWorldScenarios:
    """Test real-world scenarios with streaming and early stopping."""

    def setup_method(self):
        self.notebook = parse_notebook("""import marimo
app = marimo.App()

@app.cell
def _():
    x = 1
    return

@app.cell
def _():
    x = 2  # Multiple definitions
    return
""")

    async def test_real_rules_with_early_stopping(self):
        """Test real rules with early stopping."""
        from marimo._lint.rules.breaking import MultipleDefinitionsRule

        from marimo._lint.rules.formatting import GeneralFormattingRule

        # Stop on first runtime error
        config = EarlyStoppingConfig(stop_on_runtime=True)
        checker = RuleEngine(
            [MultipleDefinitionsRule(), GeneralFormattingRule()],
            early_stopping=config,
        )

        diagnostics = []
        async for diagnostic in checker.check_notebook_streaming(
            self.notebook
        ):
            diagnostics.append(diagnostic)
            # Should stop after first runtime error
            if diagnostic.severity == Severity.RUNTIME:
                break

        # Should have at least one runtime diagnostic (multiple definitions)
        runtime_diagnostics = [
            d for d in diagnostics if d.severity == Severity.RUNTIME
        ]
        assert len(runtime_diagnostics) > 0
