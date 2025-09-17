# Copyright 2024 Marimo. All rights reserved.
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
            # Extract positioning information from the log record
            extra_data = getattr(record, '__dict__', {})
            node_lineno = extra_data.get('node_lineno')
            node_col_offset = extra_data.get('node_col_offset', 0)

            # Parse SQL position from error message (e.g. "Line 23, Col: 32")
            message = record.getMessage()
            sql_line = None
            sql_col = None

            # Look for "Line X, Col: Y" pattern in the error message
            line_col_match = re.search(r'Line (\d+), Col: (\d+)', message)
            if line_col_match:
                sql_line = int(line_col_match.group(1)) - 1  # Convert to 0-based
                sql_col = int(line_col_match.group(2)) - 1   # Convert to 0-based

            # Calculate actual line position
            calculated_line = 0
            calculated_col = 0

            if node_lineno is not None:
                calculated_line = node_lineno - 1  # Convert to 0-based
                if sql_line is not None:
                    # For multiline SQL, add the SQL line offset
                    calculated_line += sql_line
                if sql_col is not None:
                    calculated_col = sql_col
                elif node_col_offset is not None:
                    calculated_col = node_col_offset

            await ctx.add_diagnostic(
                Diagnostic(
                    message=message,
                    line=calculated_line,
                    cell_id=None,
                    column=calculated_col,
                )
            )


class DuckdbRule(LintRule):
    """MF006: DuckDB connection and query issues.

    This rule processes log messages captured when marimo encounters issues
    with DuckDB connections or queries during dependency analysis. DuckDB
    is used for analyzing SQL dependencies and dataframe operations.

    ## What it does

    Captures DuckDB-related error logs and creates diagnostics to help
    identify connection or query issues.

    ## Why is this bad?

    DuckDB issues can lead to:
    - Failed dependency analysis for SQL cells
    - Incomplete dataframe tracking
    - Reduced accuracy of reactive execution
    - Runtime errors when SQL operations are performed

    ## Examples

    **Triggered by:**
    - DuckDB connection failures
    - Resource exhaustion during analysis
    - Incompatible DuckDB operations

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [SQL Support](https://docs.marimo.io/guides/sql/)
    """

    code = "MF006"
    name = "duckdb-error"
    description = "DuckDB connection and query issues"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process DuckDB error logs."""
        logs = ctx.get_logs(self.code)

        for record in logs:
            # Extract rich context from record extra data
            extra_data = getattr(record, '__dict__', {})
            sql_query = extra_data.get('sql_query', '')
            sql_statement = extra_data.get('sql_statement', '')
            error_type = extra_data.get('error_type', '')
            context = extra_data.get('context', '')
            node_lineno = extra_data.get('node_lineno')
            node_col_offset = extra_data.get('node_col_offset', 0)

            # Build enhanced message with context
            base_message = record.getMessage()
            message_parts = [base_message]

            if error_type:
                message_parts.append(f"Error type: {error_type}")

            if context:
                message_parts.append(f"Context: {context}")

            if sql_statement:
                message_parts.append(f"SQL statement: {sql_statement}")
            elif sql_query:
                message_parts.append(f"SQL query: {sql_query}")

            enhanced_message = " | ".join(message_parts)

            # Calculate line position from node context
            calculated_line = 0
            calculated_col = 0
            if node_lineno is not None:
                calculated_line = node_lineno - 1  # Convert to 0-based
            if node_col_offset is not None:
                calculated_col = node_col_offset

            await ctx.add_diagnostic(
                Diagnostic(
                    message=enhanced_message,
                    line=calculated_line,
                    cell_id=None,
                    column=calculated_col,
                )
            )


class MiscLogRule(LintRule):
    """MF007: Miscellaneous log messages during processing.

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

    code = "MF007"
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
