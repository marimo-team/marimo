# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.error_utils import (
    MarimoSQLException,
    exception_message_to_metadata,
    is_sql_parse_error,
    split_error_message,
)
from marimo._sql.sql import sql

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLGLOT = DependencyManager.sqlglot.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()


class TestSplitErrorMessage:
    def test_split_error_message(self):
        assert split_error_message(
            "Syntax error: SELECT * FROM nonexistent_table"
        ) == ("Syntax error", "SELECT * FROM nonexistent_table")

    def test_split_multiple_error_message(self):
        assert split_error_message(
            "Syntax error: SELECT * FROM nonexistent_table: Table with name pokemo does not exist!"
        ) == (
            "Syntax error",
            "SELECT * FROM nonexistent_table: Table with name pokemo does not exist!",
        )

    def test_split_error_message_no_colon(self):
        assert split_error_message(
            "Syntax error SELECT * FROM nonexistent_table"
        ) == (None, "Syntax error SELECT * FROM nonexistent_table")


class TestExceptionMessageToMetadata:
    def test_exception_message_to_metadata(self):
        assert exception_message_to_metadata(
            "Syntax error: SELECT * FROM nonexistent_table", "duckdb"
        ) == ("SELECT * FROM nonexistent_table", "Syntax error", None)

    def test_exception_message_with_line(self):
        result = exception_message_to_metadata(
            "Syntax error: SELECT * FROM nonexistent_table: LINE 1: SELECT * FROM nonexistent_table",
            "duckdb",
        )
        assert result == (
            "SELECT * FROM nonexistent_table:",
            "Syntax error",
            "LINE 1: SELECT * FROM nonexistent_table",
        )

        # Handle multi-line
        result = exception_message_to_metadata(
            """Syntax error: SELECT * FROM nonexistent_table
        LINE 2: SELECT * FROM nonexistent_table""",
            "duckdb",
        )
        assert result == (
            "SELECT * FROM nonexistent_table",
            "Syntax error",
            "LINE 2: SELECT * FROM nonexistent_table",
        )


class TestDuckDBRuntimeErrors:
    """Test DuckDB errors that occur during SQL execution."""

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_table_not_found_error(self):
        """Test error when referencing a non-existent table."""
        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT * FROM nonexistent_table")

        error = exc_info.value
        assert "nonexistent_table" in str(error).lower()
        assert "does not exist" in str(error).lower()
        assert (  # pyright: ignore[reportOperatorIssue]
            "LINE 1: SELECT * FROM nonexistent_table" in error.codeblock
        )

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_column_not_found_error(self):
        """Test error when referencing a non-existent column."""
        # Create a test table first
        sql("CREATE OR REPLACE TABLE test_error_table (id INTEGER, name TEXT)")

        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT invalid_column FROM test_error_table")

        error = exc_info.value
        assert "invalid_column" in str(error)
        assert (  # pyright: ignore[reportOperatorIssue]
            "LINE 1: SELECT invalid_column FROM test_error_table"
            in error.codeblock
        )

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_syntax_error_missing_from(self):
        """Test syntax error when FROM keyword is misspelled."""
        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT * FRM test_table")

        error = exc_info.value
        assert "syntax error" in str(error).lower()

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_syntax_error_malformed_expression(self):
        """Test syntax error with malformed SQL expression."""
        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT ( FROM table")

        error = exc_info.value
        assert (
            "syntax error" in str(error).lower()
            or "parser error" in str(error).lower()
        )

    @pytest.mark.skipif(
        not HAS_DUCKDB or not (HAS_PANDAS or HAS_POLARS),
        reason="DuckDB/Pandas not installed",
    )
    def test_data_type_error(self):
        """Test data type conversion errors."""
        sql("CREATE OR REPLACE TABLE test_type_table (id INTEGER)")
        sql("INSERT INTO test_type_table VALUES (1)")

        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT id / 'invalid_string' FROM test_type_table")

        error = exc_info.value
        # Error message varies by DuckDB version, just ensure we caught it
        assert len(str(error)) > 0


class TestSQLGlotParseErrors:
    """Test SQLGlot parsing errors during static analysis."""

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_malformed_case_statement(self):
        """Test ParseError with malformed CASE statement."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        with pytest.raises(ParseError):
            parse_one("SELECT CASE FROM table")

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_incomplete_cte(self):
        """Test ParseError with incomplete CTE."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        with pytest.raises(ParseError):
            parse_one("WITH cte AS (SELECT * FROM x)")

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_function_argument_errors(self):
        """Test ParseError with incorrect function arguments."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        # Too few arguments for IF function
        with pytest.raises(ParseError):
            parse_one("SELECT IF(a > 0)")

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_empty_query_parse(self):
        """Test ParseError with empty query."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        with pytest.raises(ParseError):
            parse_one("")

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_invalid_select_syntax(self):
        """Test ParseError with invalid SELECT syntax."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        with pytest.raises(ParseError):
            parse_one("SELECT * * FROM table")


class TestErrorUtilityFunctions:
    """Test marimo's SQL error handling utility functions."""

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_is_sql_parse_error_duckdb(self):
        """Test detection of DuckDB parsing errors."""
        import duckdb

        with pytest.raises(Exception) as exc_info:
            duckdb.sql("SELECT * FROM nonexistent_table")
        assert is_sql_parse_error(exc_info.value) is True

        with pytest.raises(Exception) as exc_info:
            duckdb.sql("SELECT * FRM invalid_syntax")
        assert is_sql_parse_error(exc_info.value) is True

    @pytest.mark.skipif(not HAS_SQLGLOT, reason="SQLGlot not installed")
    def test_is_sql_parse_error_sqlglot(self):
        """Test detection of SQLGlot parsing errors."""
        from sqlglot import parse_one
        from sqlglot.errors import ParseError

        with pytest.raises(ParseError) as exc_info:
            parse_one("SELECT CASE FROM table")
        assert is_sql_parse_error(exc_info.value) is True

    def test_is_sql_parse_error_non_sql_exception(self):
        """Test that non-SQL exceptions are not detected as SQL errors."""
        regular_exception = ValueError("This is not a SQL error")
        assert is_sql_parse_error(regular_exception) is False

    def test_is_sql_parse_error_marimo_sql_exception(self):
        """Test that MarimoSQLException is detected as SQL error."""
        marimo_sql_exception = MarimoSQLException(
            "SQL error message", "SQL error", "codeblock"
        )
        assert is_sql_parse_error(marimo_sql_exception) is True
