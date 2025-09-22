# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import logging

from marimo._lint.context import LintContext, RuleContext
from marimo._lint.rules.formatting.parsing import (
    MiscLogRule,
    SqlParseRule,
)
from marimo._schemas.serialization import NotebookSerialization


class TestLogRules:
    """Test log message rules and grouping."""

    def test_log_grouping_async_safe(self):
        """Test that log grouping is async-safe and works correctly."""
        # Create mock log records with different rule targets
        record1 = logging.LogRecord(
            name="marimo",
            level=logging.ERROR,
            pathname="/test.py",
            lineno=10,
            msg="SQL parse error",
            args=(),
            exc_info=None,
        )
        record1.__dict__["lint_rule"] = "MF005"

        record2 = logging.LogRecord(
            name="marimo",
            level=logging.WARNING,
            pathname="/test.py",
            lineno=30,
            msg="General warning",
            args=(),
            exc_info=None,
        )
        # No lint_rule specified - should go to MF006

        # Create minimal notebook
        notebook = NotebookSerialization(filename="test.py", cells=[], app=None)

        # Test with initial logs
        ctx = LintContext(notebook, logs=[record1, record2])
        ctx._group_initial_logs()

        # Verify logs are correctly grouped
        assert len(ctx._logs_by_rule.get("MF005", [])) == 1
        assert len(ctx._logs_by_rule.get("MF006", [])) == 1
        assert ctx._logs_by_rule["MF005"][0].getMessage() == "SQL parse error"
        assert ctx._logs_by_rule["MF006"][0].getMessage() == "General warning"

    async def test_sql_parse_rule(self):
        """Test SqlParseRule processes MF005 logs correctly."""
        record = logging.LogRecord(
            name="marimo",
            level=logging.ERROR,
            pathname="/test.py",
            lineno=20,
            msg="SQL parsing error",
            args=(),
            exc_info=None,
        )
        record.__dict__["lint_rule"] = "MF005"

        notebook = NotebookSerialization(
            filename="test.py", cells=[], app=None
        )
        ctx = LintContext(notebook, logs=[record])
        ctx._group_initial_logs()

        rule = SqlParseRule()
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)

        diagnostics = await ctx.get_diagnostics()
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "MF005"
        assert diagnostics[0].message == "SQL parsing error"

    async def test_misc_log_rule(self):
        """Test MiscLogRule processes unspecified logs correctly."""
        # WARNING level - should be processed
        record1 = logging.LogRecord(
            name="marimo",
            level=logging.WARNING,
            pathname="/test.py",
            lineno=10,
            msg="General warning",
            args=(),
            exc_info=None,
        )

        # DEBUG level - should be ignored
        record2 = logging.LogRecord(
            name="marimo",
            level=logging.DEBUG,
            pathname="/test.py",
            lineno=20,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        notebook = NotebookSerialization(
            filename="test.py", cells=[], app=None
        )
        ctx = LintContext(notebook, logs=[record1, record2])
        ctx._group_initial_logs()

        rule = MiscLogRule()
        rule_ctx = RuleContext(ctx, rule)
        await rule.check(rule_ctx)

        diagnostics = await ctx.get_diagnostics()
        # Only WARNING should create a diagnostic
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "MF006"
        assert diagnostics[0].message == "General warning"

    def test_rule_context_get_logs(self):
        """Test RuleContext.get_logs method."""
        record1 = logging.LogRecord(
            name="marimo",
            level=logging.ERROR,
            pathname="/test.py",
            lineno=10,
            msg="SQL parse error",
            args=(),
            exc_info=None,
        )
        record1.__dict__["lint_rule"] = "MF005"

        notebook = NotebookSerialization(
            filename="test.py", cells=[], app=None
        )
        ctx = LintContext(notebook, logs=[record1])
        ctx._group_initial_logs()

        rule = SqlParseRule()
        rule_ctx = RuleContext(ctx, rule)

        # Test getting specific rule logs
        mf005_logs = rule_ctx.get_logs("MF005")
        assert len(mf005_logs) == 1
        assert mf005_logs[0].getMessage() == "SQL parse error"

        # Test getting non-existent rule logs
        empty_logs = rule_ctx.get_logs("MF999")
        assert len(empty_logs) == 0

        # Test getting all logs
        all_logs = rule_ctx.get_logs(None)
        assert len(all_logs) == 1
