# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.parse import SqlParseError, SqlParseResult, parse_sql

HAS_DUCKDB = DependencyManager.duckdb.has()


def test_sql_parse_result_with_errors():
    """Test SqlParseResult with errors."""
    error = SqlParseError(
        message="Syntax error", line=1, column=5, severity="error"
    )
    result = SqlParseResult(success=False, errors=[error])

    assert result.success is False
    assert len(result.errors) == 1
    assert result.errors[0].message == "Syntax error"


class TestUnsupportedDialects:
    """Test handling of unsupported SQL dialects."""

    @pytest.mark.parametrize(
        "dialect",
        [
            "postgresql",
            "mysql",
            "sqlite",
            "oracle",
            "sqlserver",
            "bigquery",
            "snowflake",
            "redshift",
            "",
            "unknown_dialect",
        ],
    )
    def test_unsupported_dialects_return_success(self, dialect: str):
        """Test that unsupported dialects return successful parse results."""
        result, error = parse_sql("SELECT * FROM table", dialect)
        assert result is not None
        assert error is None

        assert isinstance(result, SqlParseResult)
        assert result.success is True
        assert result.errors == []

    def test_dialect_with_whitespace(self):
        """Test dialects with leading/trailing whitespace."""
        result, error = parse_sql("SELECT 1", "  postgresql  ")

        assert result is not None
        assert error is None

        assert result.success is True
        assert result.errors == []


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
class TestDuckDBValidQueries:
    """Test parsing of valid SQL queries with DuckDB."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT 1",
            "SELECT 1 as value",
            "SELECT 'hello' as greeting",
            "SELECT 1, 2, 3",
            "SELECT 1 as a, 2 as b, 3 as c",
            "SELECT 1 UNION SELECT 2",
            "SELECT CASE WHEN 1 > 0 THEN 'positive' ELSE 'zero or negative' END",
            "SELECT COUNT(*)",
            "SELECT SUM(1), AVG(1), MAX(1), MIN(1)",
            "SELECT 1 ORDER BY 1",
            "SELECT 1 LIMIT 10",
        ],
    )
    def test_valid_queries_return_success(self, query: str):
        """Test that valid SQL queries return successful parse results."""
        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert isinstance(result, SqlParseResult)
        assert result.success is True
        assert result.errors == []

    @pytest.mark.parametrize(
        "dialect",
        [
            "duckdb",
            "DUCKDB",
            "DuckDB",
            "  duckdb  ",
        ],
    )
    def test_duckdb_dialect_variations(self, dialect: str):
        """Test that various DuckDB dialect strings work."""
        result, error = parse_sql("SELECT * FROM", dialect)
        assert result is not None
        assert error is None

        assert result.success is False

    def test_multiline_valid_query(self):
        """Test parsing multiline valid queries."""
        query = """
        SELECT
            1 as id,
            'test' as name,
            true as active
        ORDER BY id DESC
        """

        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert result.success is True
        assert result.errors == []

    def test_query_with_comments(self):
        """Test parsing queries with SQL comments."""
        query = """
        -- This is a comment
        SELECT 1 as test_column; -- End line comment
        """

        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert result.success is True
        assert result.errors == []

    def test_complex_valid_query(self):
        """Test parsing a complex but valid query."""
        query = """
        WITH summary AS (
            SELECT
                1 as id,
                100 as total_quantity,
                50.5 as avg_price
        )
        SELECT
            id,
            total_quantity,
            avg_price,
            CASE
                WHEN total_quantity > 100 THEN 'High Volume'
                WHEN total_quantity > 50 THEN 'Medium Volume'
                ELSE 'Low Volume'
            END as volume_category
        FROM summary
        ORDER BY total_quantity DESC
        """

        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert result.success is True
        assert result.errors == []


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
class TestDuckDBInvalidQueries:
    """Test parsing of invalid SQL queries with DuckDB."""

    @pytest.mark.parametrize(
        ("query", "expected_error_keywords"),
        [
            ("SELECT * FRM table", ["syntax", "error"]),
            ("SELECT (", ["syntax", "error"]),
            ("SELECT * FROM", ["syntax", "error"]),
            ("SELECT ,", ["syntax", "error"]),
            ("SELEC * FROM table", ["syntax", "error"]),
            ("SELECT * FROM table WHERE", ["syntax", "error"]),
            ("SELECT * FROM table ORDER", ["syntax", "error"]),
            ("INSERT INTO", ["syntax", "error"]),
            ("UPDATE", ["syntax", "error"]),
            ("DELETE", ["syntax", "error"]),
            # Unclosed parentheses
            ("SELECT COUNT(*", ["syntax", "error"]),
            # Unclosed quotes
            ("SELECT 'unclosed string", ["syntax", "error"]),
            # Invalid function call
            ("SELECT COUNT(DISTINCT)", ["syntax", "error"]),
            # Malformed CASE statement
            ("SELECT CASE WHEN FROM table", ["syntax", "error"]),
            # Incomplete JOIN
            ("SELECT * FROM table1 JOIN", ["syntax", "error"]),
        ],
    )
    def test_invalid_queries_return_errors(
        self, query: str, expected_error_keywords: list[str]
    ):
        """Test that invalid SQL queries return error results."""
        result = parse_sql(query, "duckdb")

        assert isinstance(result, SqlParseResult)
        assert result.success is False
        assert len(result.errors) > 0

        error = result.errors[0]
        assert isinstance(error, SqlParseError)
        assert error.severity == "error"
        assert error.line > 0
        assert error.column >= 0

        # Check that error message contains expected keywords
        error_msg_lower = error.message.lower()
        assert any(
            keyword in error_msg_lower for keyword in expected_error_keywords
        )


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
class TestErrorPositionCalculation:
    """Test that error positions (line and column) are calculated correctly."""

    def test_single_line_error_position(self):
        """Test position calculation for single-line queries."""
        query = "SELECT * FRM table"  # Error at position of "FRM"

        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert result.success is False
        assert len(result.errors) == 1

        error = result.errors[0]
        assert error.line == 1
        assert error.column > 0  # Column should be reasonable

    def test_multiline_error_position(self):
        """Test position calculation for multiline queries."""
        query = """SELECT name,
        email,
        FRM users"""  # Error on line 3

        result, error = parse_sql(query, "duckdb")
        assert result is not None

        assert result.success is False
        assert len(result.errors) == 1

        error = result.errors[0]
        assert error.line == 3
        assert error.column == 0

    def test_error_at_beginning_of_line(self):
        """Test position calculation when error is at beginning of line."""
        query = """SELECT *
FRM table"""

        result, error = parse_sql(query, "duckdb")
        assert result is not None

        assert result.success is False
        assert len(result.errors) == 1

        error = result.errors[0]
        assert error.line == 2
        assert error.column == 0

    def test_error_with_leading_whitespace(self):
        """Test position calculation with leading whitespace."""
        query = """    SELECT *
    FRM table"""

        result, error = parse_sql(query, "duckdb")
        assert result is not None

        assert result.success is False
        assert len(result.errors) == 1

        error = result.errors[0]
        assert error.line == 2

    def test_error_position_after_newlines(self):
        """Test position calculation with multiple newlines."""
        query = """
        SELECT name
        FROM users
        WHERE invalid_syntax"""

        result, error = parse_sql(query, "duckdb")
        assert result is not None
        assert error is None

        assert result.success is False
        assert len(result.errors) == 1

        error = result.errors[0]
        assert error.line == 3
        assert error.column >= 0


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query(self):
        """Test parsing empty query."""
        result, error = parse_sql("", "duckdb")
        assert result is not None
        assert error is None

        assert isinstance(result, SqlParseResult)
        assert result.success is True

    def test_whitespace_only_query(self):
        """Test parsing query with only whitespace."""
        result, error = parse_sql("   \n  \t  ", "duckdb")
        assert result is not None
        assert error is None

        assert isinstance(result, SqlParseResult)
        assert result.success is True
        assert result.errors == []

    def test_query_with_semicolon(self):
        """Test parsing query with trailing semicolon."""
        result, error = parse_sql("SELECT 1;", "duckdb")
        assert result is not None

        assert result.success is True
        assert result.errors == []

    def test_multiple_statements(self):
        """Test parsing multiple SQL statements."""
        query = "SELECT 1; SELECT 2;"

        result, error = parse_sql(query, "duckdb")

        # DuckDB might handle this differently, just ensure we get a result
        assert isinstance(result, SqlParseResult)

    def test_very_long_query(self):
        """Test parsing a very long query."""
        # Create a query with many columns
        columns = ", ".join([f"{i} as col_{i}" for i in range(100)])
        query = f"SELECT {columns}"

        result, error = parse_sql(query, "duckdb")
        assert error is None

        assert result is not None
        assert result.success is True
        assert result.errors == []

    def test_query_with_unicode(self):
        """Test parsing query with Unicode characters."""
        query = "SELECT 'Hello 世界' as greeting"

        result, error = parse_sql(query, "duckdb")
        assert error is None

        assert result is not None
        assert result.success is True
        assert result.errors == []

    def test_query_with_special_characters(self):
        """Test parsing query with various special characters."""
        query = "SELECT 'test@#$%^&*()' as special_chars"

        result, error = parse_sql(query, "duckdb")
        assert error is None

        assert result is not None
        assert result.success is True
        assert result.errors == []

    def test_deeply_nested_query(self):
        """Test parsing deeply nested subqueries."""
        query = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT 1 as nested_value
                ) inner_query
            ) middle_query
        ) outer_query
        """

        result, error = parse_sql(query, "duckdb")
        assert error is None

        assert result is not None
        assert result.success is True
        assert result.errors == []
