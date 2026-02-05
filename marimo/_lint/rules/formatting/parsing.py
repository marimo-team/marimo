# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class StdoutRule(LintRule):
    """MF002: Parse captured stdout during notebook loading.

    This rule processes any output that was captured from stdout while marimo
    was parsing and loading a notebook file. Stdout output during parsing
    typically indicates warnings or informational messages from the Python
    interpreter or imported modules.

    ## What it does

    Captures and parses stdout output during notebook loading, looking for
    structured warning messages that include file and line number references.
    Creates diagnostics from any warnings or messages found.

    ## Why is this bad?

    While stdout output doesn't prevent execution, it often indicates:
    - Deprecation warnings from imported libraries
    - Configuration issues
    - Potential compatibility problems
    - Code that produces unexpected side effects during import

    ## Examples

    **Captured stdout:**
    ```
    notebook.py:15: DeprecationWarning: 'imp' module is deprecated
    ```

    **Result:** Creates a diagnostic pointing to line 15 with the deprecation warning.

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MF002"
    name = "parse-stdout"
    description = "Parse captured stdout during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process captured stdout and create diagnostics."""
        # Pattern to match file:line format (e.g., "file.py:68: SyntaxWarning")
        line_pattern = re.compile(r"([^:]+):(\d+):\s*(.+)")

        # Split stderr by lines to handle multiple warnings
        lines = ctx.stdout.strip().split("\n")
        captured = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line contains a file:line reference
            match = line_pattern.match(line)
            if match:
                captured = True
                _, line_num_str, warning_msg = match.groups()
                await ctx.add_diagnostic(
                    Diagnostic(
                        message=warning_msg,
                        line=int(line_num_str) - 1,  # Convert to 0-based index
                        cell_id=None,
                        column=0,
                    )
                )

        # Fallback: if no line patterns found, create single diagnostic
        if not captured and ctx.stdout:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"Parsing warning: {ctx.stderr}",
                    cell_id=None,
                    line=0,
                    column=0,
                )
            )


class StderrRule(LintRule):
    """MF003: Parse captured stderr during notebook loading.

    This rule processes any output that was captured from stderr while marimo
    was parsing and loading a notebook file. Stderr output typically contains
    warnings and error messages from the Python interpreter, such as syntax
    warnings, deprecation notices, and import errors.

    ## What it does

    Captures stderr output during notebook loading and creates diagnostics
    from any error messages or warnings. This helps identify potential
    issues that don't prevent parsing but may affect runtime behavior.

    ## Why is this bad?

    Stderr output during parsing often indicates:
    - Syntax warnings (like invalid escape sequences)
    - Import warnings or errors
    - Deprecation notices from libraries
    - Configuration issues that might affect execution

    While these don't break the notebook, they can lead to unexpected
    behavior or indicate code that needs updating.

    ## Examples

    **Captured stderr:**
    ```
    notebook.py:68: SyntaxWarning: invalid escape sequence '\\l'
    ```

    **Result:** Creates a diagnostic pointing to line 68 about the invalid escape sequence.

    **Common issues:**
    - Raw strings needed: `r"\\path\\to\\file"` instead of `"\\path\\to\\file"`
    - Deprecated library usage
    - Missing import dependencies

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Python Warning Categories](https://docs.python.org/3/library/warnings.html#warning-categories)
    """

    code = "MF003"
    name = "parse-stderr"
    description = "Parse captured stderr during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        # Process stderr content
        if ctx.stderr:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"stderr: {ctx.stderr}",
                    cell_id=None,
                    line=0,
                    column=0,
                )
            )


class SqlParseRule(LintRule):
    """MF005: SQL parsing errors during dependency analysis.

    This rule processes log messages captured when marimo encounters errors
    while parsing SQL statements in notebook cells. SQL parsing is used for
    dependency analysis and dataframe tracking.

    ## What it does

    Captures SQL parsing error logs and creates diagnostics pointing to
    problematic SQL statements in cells.

    ## Why is this bad?

    SQL parsing failures can lead to:
    - Incorrect dependency analysis for SQL-using cells
    - Missing dataframe references in dependency graph
    - Reduced effectiveness of reactive execution
    - Potential runtime errors when SQL is executed

    ## Examples

    **Triggered by:**
    - Invalid SQL syntax in cell code
    - Unsupported SQL dialects or extensions
    - Complex SQL that exceeds parser capabilities

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [SQL Support](https://docs.marimo.io/guides/sql/)
    """

    code = "MF005"
    name = "sql-parse-error"
    description = "SQL parsing errors during dependency analysis"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process SQL parsing error logs."""
        logs = ctx.get_logs(self.code)

        for record in logs:
            # Extract metadata from log record - ONLY use extra_data
            extra_data = getattr(record, "__dict__", {})

            # Use clean message from metadata (without SQL trace)
            message = extra_data.get("clean_message", "SQL parsing error")

            # Calculate line position using cell information
            cell_lineno = extra_data.get(
                "cell_lineno", 0
            )  # Cell start line in notebook
            node_lineno = extra_data.get(
                "node_lineno", 1
            )  # Node line within cell
            sql_line = extra_data.get("sql_line")  # SQL line within SQL string

            # Start with cell position + node position within cell
            line = cell_lineno + node_lineno - 1  # Convert to 0-based

            # Add SQL line offset if available
            if sql_line is not None:
                line += sql_line

            # Use SQL column if available, otherwise node column
            sql_col = extra_data.get("sql_col")
            col = (
                sql_col
                if sql_col is not None
                else extra_data.get("node_col_offset", 0)
            )

            await ctx.add_diagnostic(
                Diagnostic(
                    message=message,
                    line=line,
                    cell_id=None,
                    column=col,
                )
            )


class MiscLogRule(LintRule):
    """MF006: Miscellaneous log messages during processing.

    This rule processes log messages that don't have a specific rule assigned
    but may still be relevant for understanding notebook health and potential
    issues during processing.

    ## What it does

    Captures warning and error level log messages that aren't handled by
    other specific log rules and creates diagnostics to surface them.

    ## Why is this bad?

    Unhandled log messages may indicate:
    - Unexpected issues during notebook processing
    - Configuration problems
    - Library warnings that affect execution
    - Performance or resource issues

    ## Examples

    **Triggered by:**
    - General warnings from imported libraries
    - Configuration issues
    - Unexpected errors during processing

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MF006"
    name = "misc-log-capture"
    description = "Miscellaneous log messages during processing"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process miscellaneous log messages."""
        logs = ctx.get_logs(self.code)

        for record in logs:
            # Only process WARNING and ERROR level logs to avoid noise
            if record.levelno < logging.WARNING:
                continue

            await ctx.add_diagnostic(
                Diagnostic(
                    message=record.getMessage(),
                    line=0,  # Misc logs don't have meaningful line positioning
                    cell_id=None,
                    column=0,
                )
            )
