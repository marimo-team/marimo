# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.errors import MarimoSQLError
from marimo._sql.error_utils import (
    MarimoSQLException,
    create_sql_error_from_exception,
    extract_sql_position,
    is_sql_parse_error,
)
from marimo._sql.sql import sql

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLGLOT = DependencyManager.sqlglot.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()


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
        assert error.sql_statement == "SELECT * FROM nonexistent_table"

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_column_not_found_error(self):
        """Test error when referencing a non-existent column."""
        # Create a test table first
        sql("CREATE OR REPLACE TABLE test_error_table (id INTEGER, name TEXT)")

        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT invalid_column FROM test_error_table")

        error = exc_info.value
        assert "invalid_column" in str(error)
        assert "test_error_table" in error.sql_statement

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_syntax_error_missing_from(self):
        """Test syntax error when FROM keyword is misspelled."""
        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT * FRM test_table")

        error = exc_info.value
        assert "syntax error" in str(error).lower()
        assert "SELECT * FRM test_table" in error.sql_statement

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

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_long_sql_statement_truncation(self):
        """Test that long SQL statements are truncated in error messages."""
        long_query = (
            "SELECT "
            + ", ".join([f"col_{i}" for i in range(100)])
            + " FROM nonexistent_table"
        )

        with pytest.raises(MarimoSQLException) as exc_info:
            sql(long_query)

        error = exc_info.value
        # Should be truncated to ~200 chars + "..."
        assert len(error.sql_statement) <= 203
        if len(long_query) > 200:
            assert error.sql_statement.endswith("...")


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
        marimo_sql_exception = MarimoSQLException("SQL error message")
        assert is_sql_parse_error(marimo_sql_exception) is True

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_create_sql_error_from_exception(self):
        """Test conversion of raw exception to MarimoSQLError."""
        import duckdb

        class MockCell:
            def __init__(self, sql_statement: str):
                self.sqls = [sql_statement]

        try:
            duckdb.sql("SELECT * FROM nonexistent_table")
        except Exception as e:
            mock_cell = MockCell("SELECT * FROM nonexistent_table")
            error = create_sql_error_from_exception(e, mock_cell)

            assert isinstance(error, MarimoSQLError)
            assert "nonexistent_table" in error.sql_statement
            assert len(error.msg) > 0
            assert "nonexistent_table" in error.msg
            # Hint field should exist (may be None for this error)
            assert hasattr(error, "hint")

    def test_create_sql_error_long_statement(self):
        """Test SQL statement truncation in error creation."""
        import duckdb

        long_statement = (
            "SELECT "
            + ", ".join([f"col_{i}" for i in range(100)])
            + " FROM test"
        )

        class MockCell:
            def __init__(self, sql_statement: str):
                self.sqls = [sql_statement]

        try:
            duckdb.sql(long_statement)
        except Exception as e:
            mock_cell = MockCell(long_statement)
            error = create_sql_error_from_exception(e, mock_cell)

            # Should be truncated
            assert len(error.sql_statement) <= 203
            if len(long_statement) > 200:
                assert error.sql_statement.endswith("...")


class TestErrorMessageQuality:
    """Test that error messages are actionable and well-formatted."""

    def test_extract_sql_position_duckdb_format(self):
        """Test position extraction from DuckDB error messages."""
        # DuckDB format: "Line 1, Col: 15"
        duckdb_msg = "Parser Error: syntax error at Line 1, Col: 15"
        line, col = extract_sql_position(duckdb_msg)
        assert line == 0  # 0-based
        assert col == 14  # 0-based

    def test_extract_sql_position_sqlglot_format(self):
        """Test position extraction from SQLGlot error messages."""
        # SQLGlot format variations
        sqlglot_msg = "Parse error at line 2, col 10"
        line, col = extract_sql_position(sqlglot_msg)
        assert line == 1  # 0-based
        assert col == 9  # 0-based

    def test_extract_sql_position_no_position(self):
        """Test position extraction when no position info available."""
        no_position_msg = "Some generic SQL error without position"
        line, col = extract_sql_position(no_position_msg)
        assert line is None
        assert col is None

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_error_message_enhancement(self):
        """Test that error messages are enhanced with prefixes."""
        import duckdb

        class MockCell:
            sqls = ["SELECT * FRM invalid"]

        try:
            duckdb.sql("SELECT * FRM invalid")
        except Exception as e:
            error = create_sql_error_from_exception(e, MockCell())
            # Should have "SQL syntax error:" prefix for ParserException
            assert error.msg.startswith(
                "SQL syntax error:"
            ) or error.msg.startswith("SQL parse error:")

    def test_error_message_cleaning(self):
        """Test that error messages are cleaned of traces."""

        class MockException(Exception):
            def __str__(self):
                return "SQL error message\nTraceback (most recent call last):\n  File..."

        class MockCell:
            sqls = ["SELECT * FROM test"]

        error = create_sql_error_from_exception(MockException(), MockCell())
        # Should only contain the first line, no traceback
        assert "Traceback" not in error.msg
        assert error.msg == "SQL error message"


class TestIntegrationAndEdgeCases:
    """Test complete error flow and edge cases."""

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_sql_function_error_flow(self):
        """Test complete error flow through mo.sql() function."""
        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT * FROM definitely_nonexistent_table_12345")

        error = exc_info.value
        assert isinstance(error, MarimoSQLException)
        assert error.sql_statement is not None
        assert len(error.sql_statement) > 0

    def test_empty_sql_statement_error_handling(self):
        """Test error handling with empty SQL statements."""

        class MockCell:
            sqls = []

        mock_exception = Exception("Test error")
        error = create_sql_error_from_exception(mock_exception, MockCell())

        assert error.sql_statement == ""

    def test_cell_without_sqls_attribute(self):
        """Test error handling when cell doesn't have sqls attribute."""

        class MockCellNoSqls:
            pass

        mock_exception = Exception("Test error")
        error = create_sql_error_from_exception(
            mock_exception, MockCellNoSqls()
        )

        assert error.sql_statement == ""

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_multiple_errors_in_sequence(self):
        """Test handling multiple SQL errors in sequence."""
        # First error
        with pytest.raises(MarimoSQLException):
            sql("SELECT * FROM table1_nonexistent")

        # Second error should still work
        with pytest.raises(MarimoSQLException):
            sql("SELECT * FROM table2_nonexistent")

    def test_error_with_special_characters(self):
        """Test error handling with SQL containing special characters."""
        with pytest.raises(MarimoSQLException):
            sql("SELECT * FROM 'table with spaces and quotes'")

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_duckdb_hints_preserved(self):
        """Test that DuckDB hints like 'Did you mean?' are preserved in error messages."""
        import duckdb

        # Create a table to generate "Did you mean?" suggestions
        duckdb.sql(
            "CREATE OR REPLACE TABLE test_hints_table (id INT, name TEXT)"
        )

        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT * FROM test_hint")  # Missing 's' in table name

        error = exc_info.value
        error_msg = str(error)
        # Check that the main error message is present
        assert "does not exist" in error_msg
        # Check that the hint is properly extracted to the hint field
        assert error.hint is not None
        assert (
            "Did you mean" in error.hint or "candidate" in error.hint.lower()
        )

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_column_candidates_preserved(self):
        """Test that column candidate hints are preserved in error messages."""
        import duckdb

        # Create a table to generate candidate binding suggestions
        duckdb.sql(
            "CREATE OR REPLACE TABLE test_columns (id INT, user_name TEXT, email TEXT)"
        )

        with pytest.raises(MarimoSQLException) as exc_info:
            sql("SELECT fullname FROM test_columns")  # Wrong column name

        error = exc_info.value
        error_msg = str(error)
        # Check that the main error message is present
        assert "not found" in error_msg
        # Check that the hint is properly extracted to the hint field
        assert error.hint is not None
        assert "Candidate" in error.hint or "candidate" in error.hint.lower()

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_hint_field_in_sql_error_struct(self):
        """Test that MarimoSQLError struct properly includes hint field."""
        import duckdb

        # Create table for hint generation
        duckdb.sql(
            "CREATE OR REPLACE TABLE hint_test_table (id INT, name TEXT)"
        )

        try:
            duckdb.sql("SELECT * FROM hint_test")  # Missing letters
        except Exception as e:

            class MockCell:
                sqls = ["SELECT * FROM hint_test"]

            error_struct = create_sql_error_from_exception(e, MockCell())

            # Verify the struct has the hint field and it's populated
            assert hasattr(error_struct, "hint")
            assert error_struct.hint is not None
            assert (
                "Did you mean" in error_struct.hint
                or "candidate" in error_struct.hint.lower()
            )
            # Main message should not contain the hint
            assert error_struct.hint not in error_struct.msg

    @pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
    def test_multiline_hints_preserved(self):
        """Test that multiline hints like function candidates are fully captured."""
        import duckdb

        # Create table for multiline hint generation
        duckdb.sql(
            "CREATE OR REPLACE TABLE hint_multiline_table (id INT, name TEXT)"
        )

        try:
            duckdb.sql(
                "SELECT SUBSTRING(name) FROM hint_multiline_table"
            )  # Wrong args
        except Exception as e:

            class MockCell:
                sqls = ["SELECT SUBSTRING(name) FROM hint_multiline_table"]

            error_struct = create_sql_error_from_exception(e, MockCell())

            # Verify multiline hint is captured completely
            assert hasattr(error_struct, "hint")
            assert error_struct.hint is not None
            assert "Candidate functions:" in error_struct.hint
            assert "substring(VARCHAR, BIGINT, BIGINT)" in error_struct.hint
            assert "substring(VARCHAR, BIGINT)" in error_struct.hint
            # Should be multiline
            assert "\n" in error_struct.hint
            # Main message should be clean
            assert "Candidate functions:" not in error_struct.msg
