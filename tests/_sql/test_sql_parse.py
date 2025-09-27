# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from textwrap import dedent

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.parse import (
    SqlParseError,
    SqlParseResult,
    parse_sql,
    replace_brackets_with_quotes,
)

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
    def test_unsupported_dialects_return_none(self, dialect: str):
        """Test that unsupported dialects return none."""
        result, error = parse_sql("SELECT * FROM table", dialect)
        assert result is None
        assert error == "Unsupported dialect: " + dialect

    def test_dialect_with_whitespace(self):
        """Test dialects with leading/trailing whitespace."""
        result, error = parse_sql("SELECT 1", "  postgresql  ")

        assert result is None
        assert error == "Unsupported dialect: postgresql"

        result, error = parse_sql("SELECT 1", " duckdb ")
        assert result is not None
        assert error is None


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
            # ("SELECT 'unclosed string", ["syntax", "error"]), # DuckDB does not raise errors for this case
            # # Invalid function call
            ("SELECT COUNT(DISTINCT)", ["syntax", "error"]),
            # # Malformed CASE statement
            ("SELECT CASE WHEN FROM table", ["syntax", "error"]),
            # # Incomplete JOIN
            ("SELECT * FROM table1 JOIN", ["syntax", "error"]),
        ],
    )
    def test_invalid_queries_return_errors(
        self, query: str, expected_error_keywords: list[str]
    ):
        """Test that invalid SQL queries return error results."""
        result, error = parse_sql(query, "duckdb")

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

    def assert_line_column(
        self,
        result: SqlParseResult | None,
        parse_error: str | None,
        expected_line: int,
        expected_column: int,
    ):
        assert result is not None
        assert parse_error is None

        assert result.success is False
        assert len(result.errors) == 1
        error = result.errors[0]

        assert error.line == expected_line
        assert error.column == expected_column

    def test_single_line_error_position(self):
        """Test position calculation for single-line queries."""
        query = "SELECT * FRM table"  # Error at position of "FRM"

        result, error = parse_sql(query, "duckdb")
        self.assert_line_column(result, error, 1, 13)

    @pytest.mark.xfail(reason="DuckDB does not raise errors for this case")
    def test_multiline_error_position(self):
        """Test position calculation for multiline queries."""
        query = """SELECT name,
        email,
        FRM users"""  # Error on line 3

        result, error = parse_sql(query, "duckdb")
        self.assert_line_column(result, error, 3, 0)

    def test_error_at_beginning_of_line(self):
        """Test position calculation when error is at beginning of line."""
        query = """SELECT *
FRM table"""

        result, error = parse_sql(query, "duckdb")
        self.assert_line_column(result, error, 2, 4)

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

    @pytest.mark.xfail(
        reason="DuckDB does not raise errors for invalid syntax"
    )
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

    def test_error_position_after_offset(self):
        """Test position calculation with offset."""
        query = """SELECT id FRM users"""
        result, error = parse_sql(query, "duckdb")

        expected_line = 1
        expected_column = 14
        self.assert_line_column(result, error, expected_line, expected_column)

        query_with_brackets = "SELECT {id} FRM users"
        result, error = parse_sql(query_with_brackets, "duckdb")
        # Add 2 for the brackets
        self.assert_line_column(
            result, error, expected_line, expected_column + 2
        )

        # Multiple brackets
        query_with_multiple_vars = "SELECT id, name FRM users"
        result, error = parse_sql(query_with_multiple_vars, "duckdb")

        expected_line = 1
        expected_column = 20
        self.assert_line_column(result, error, expected_line, expected_column)

        query_multiple_vars_brackets = "SELECT {id}, {name} FRM users"
        result, error = parse_sql(query_multiple_vars_brackets, "duckdb")
        self.assert_line_column(
            result,
            error,
            expected_line,
            expected_column + (2 * 2),  # 2 for each bracket
        )

    def test_offset_after_position(self):
        query = "SELECT * FRM users WHERE id = id"
        result, error = parse_sql(query, "duckdb")
        expected_column = 13
        expected_line = 1
        self.assert_line_column(result, error, expected_line, expected_column)

        query_with_brackets = "SELECT * FRM users WHERE id = {id}"
        result, error = parse_sql(query_with_brackets, "duckdb")
        # No change since the error is before the brackets
        self.assert_line_column(result, error, expected_line, expected_column)

        # Multiple variables with brackets
        query_multiple_vars_brackets = (
            "SELECT * FRM users WHERE id = id and name = name"
        )
        result, error = parse_sql(query_multiple_vars_brackets, "duckdb")
        self.assert_line_column(result, error, expected_line, expected_column)

        query_multiple_vars_brackets_with_brackets = (
            "SELECT * FRM users WHERE id = {id} and name = {name}"
        )
        result, error = parse_sql(
            query_multiple_vars_brackets_with_brackets, "duckdb"
        )
        self.assert_line_column(result, error, expected_line, expected_column)

    def test_mixed_position_brackets(self):
        query = "SELECT id FRM users WHERE name = name"
        result, error = parse_sql(query, "duckdb")
        expected_line = 1
        expected_column = 14
        self.assert_line_column(result, error, expected_line, expected_column)

        query_with_brackets = "SELECT {id} FRM users WHERE name = {name}"
        result, error = parse_sql(query_with_brackets, "duckdb")

        self.assert_line_column(
            result,
            error,
            expected_line,
            # Only accounts for brackets before the errors
            expected_column + 2,
        )

    def test_multiline_brackets_before_error(self):
        query = """SELECT id
FRM users"""
        result, error = parse_sql(query, "duckdb")
        expected_line = 2
        expected_column = 4
        self.assert_line_column(result, error, expected_line, expected_column)

        query_with_brackets = """SELECT {id}
FRM users"""
        result, error = parse_sql(query_with_brackets, "duckdb")
        self.assert_line_column(result, error, expected_line, expected_column)

    @pytest.mark.xfail(
        reason="There is an incorrect calculation for column position"
    )
    def test_brackets_on_error_line(self):
        # Brackets on error line
        query_error_line = """SELECT name,
id FRM users"""
        result, error = parse_sql(query_error_line, "duckdb")
        expected_line = 2
        expected_column = 7
        self.assert_line_column(result, error, expected_line, expected_column)

        query_error_line_with_brackets = """SELECT {name},
{id} FRM users"""
        result, error = parse_sql(query_error_line_with_brackets, "duckdb")
        self.assert_line_column(
            result, error, expected_line, expected_column + 2
        )

    def test_multiline_brackets_after_error(self):
        query = """SELECT *
FRM users WHERE name = name"""
        result, error = parse_sql(query, "duckdb")
        expected_line = 2
        expected_column = 4
        self.assert_line_column(result, error, expected_line, expected_column)

        query_with_brackets = """SELECT *
FRM users WHERE name = {name}"""
        result, error = parse_sql(query_with_brackets, "duckdb")
        # No change since the error is after the brackets
        self.assert_line_column(result, error, expected_line, expected_column)


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

    def test_just_comments(self):
        """Test parsing query with just comments."""
        for query in [
            """
            -- This is a comment
            /* This is a comment */
            """,
            """-- SELECT 1""",
            """/* SELECT 1 */""",
            """
            -- This is a comment
            SELECT 1 as test_column; -- End line comment
            """,
            """
            /* This is a comment */
            SELECT 1 as test_column; /* End line comment */
            """,
        ]:
            result, error = parse_sql(query, "duckdb")
            assert result is not None
            assert result.success is True
            assert result.errors == []


@pytest.mark.skipif(HAS_DUCKDB, reason="DuckDB is installed")
def test_fails_gracefully_no_duckdb():
    """Test that the function fails gracefully if DuckDB is not installed."""
    result, error = parse_sql("SELECT 1", "duckdb")
    assert result is None
    assert error is not None


class TestReplaceBracketsWithQuotes:
    """Test the replace_brackets_with_quotes function."""

    def test_basic_replacement(self):
        """Test basic bracket replacement."""
        sql = "SELECT {id} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{id}' FROM users"
        assert offset_record == {7: 2}

    def test_already_quoted_single(self):
        """Test that already single-quoted brackets are not modified."""
        sql = "SELECT {id}, '{name}' FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{id}', '{name}' FROM users"
        assert offset_record == {7: 2}

    def test_already_quoted_double(self):
        """Test that already double-quoted brackets are not modified."""
        sql = 'SELECT {id}, "{name}" FROM users'
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{id}', \"{name}\" FROM users"
        assert offset_record == {7: 2}

    def test_multiple_brackets(self):
        """Test multiple unquoted brackets."""
        sql = "SELECT {id}, {name}, {age} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{id}', '{name}', '{age}' FROM users"
        assert offset_record == {7: 2, 13: 2, 21: 2}

    def test_mixed_quoted_and_unquoted(self):
        """Test mix of quoted and unquoted brackets."""
        sql = "SELECT {id}, '{name}', {age}, \"{city}\" FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert (
            result_sql
            == "SELECT '{id}', '{name}', '{age}', \"{city}\" FROM users"
        )
        assert offset_record == {7: 2, 23: 2}

    def test_no_brackets(self):
        """Test SQL with no brackets."""
        sql = "SELECT id, name FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT id, name FROM users"
        assert offset_record == {}

    def test_empty_brackets(self):
        """Test SQL with empty brackets."""
        sql = "SELECT {} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{}' FROM users"
        assert offset_record == {7: 2}

    def test_multiple_bracket_in_quotes(self):
        sql = "SELECT '{id} {name}' FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT '{id} {name}' FROM users"
        assert offset_record == {}

    def test_escaped_quotes_in_strings(self):
        """Test that escaped quotes in strings are handled correctly."""
        sql = "SELECT 'O\\'Brien', {id} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == "SELECT 'O\\'Brien', '{id}' FROM users"
        assert offset_record == {19: 2}

    def test_complex_nested_quotes(self):
        """Test complex nested quote scenarios."""
        sql = "SELECT '{id}', \"{name}\", {status} FROM users WHERE name = 'John\\'s'"
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert (
            result_sql
            == "SELECT '{id}', \"{name}\", '{status}' FROM users WHERE name = 'John\\'s'"
        )
        assert offset_record == {25: 2}

    def test_multiline(self):
        """Test multiline query."""
        sql = """
        SELECT
        {id}, {name}, {age}
        FROM users
        WHERE name = 'John\\'s'
        """
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert (
            result_sql
            == """
        SELECT
        '{id}', '{name}', '{age}'
        FROM users
        WHERE name = 'John\\'s'
        """
        )
        assert offset_record == {24: 2, 30: 2, 38: 2}

        sql = """SELECT
{id}
FROM users"""
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert (
            result_sql
            == """SELECT
'{id}'
FROM users"""
        )
        assert offset_record == {7: 2}

        sql = dedent("""
        SELECT
            {id}
        FROM users
        """)
        result_sql, offset_record = replace_brackets_with_quotes(sql)

        assert result_sql == dedent("""
        SELECT
            '{id}'
        FROM users
        """)
        assert offset_record == {12: 2}

    def test_insert_json(self):
        query = "INSERT INTO users VALUES (1, '{\"id\": 1}')"
        result_sql, offset_record = replace_brackets_with_quotes(query)

        assert result_sql == "INSERT INTO users VALUES (1, '{\"id\": 1}')"
        assert offset_record == {}

    def test_brackets_inside_quotes(self):
        # Brackets inside single quotes should not be replaced
        query = "SELECT '{id}' FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id}' FROM users"
        assert offset_record == {}

        # Brackets inside double quotes should not be replaced
        query = 'SELECT "{id}" FROM users'
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == 'SELECT "{id}" FROM users'
        assert offset_record == {}

    def test_multiple_brackets_on_same_line(self):
        query = "SELECT {id}, {name}, {age} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id}', '{name}', '{age}' FROM users"
        assert offset_record == {7: 2, 13: 2, 21: 2}

    @pytest.mark.xfail(reason="Nested brackets are not supported")
    def test_nested_brackets(self):
        query = "SELECT {id_{nested}} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id_{nested}}' FROM users"
        assert offset_record == {7: 2}

    def test_brackets_with_escaped_quotes(self):
        # Brackets inside a quoted string with escaped quotes
        query = "SELECT '{id}\\'s' FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id}\\'s' FROM users"
        assert offset_record == {}

    def test_brackets_at_start_and_end(self):
        query = "{id} FROM users WHERE name = {name}"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "'{id}' FROM users WHERE name = '{name}'"
        assert offset_record == {0: 2, 29: 2}

    def test_brackets_with_special_characters(self):
        query = "SELECT {id_1$-foo} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id_1$-foo}' FROM users"
        assert offset_record == {7: 2}

    def test_brackets_in_comment(self):
        # Brackets in SQL comments should be replaced, as comments are not parsed
        query = "SELECT id -- {comment}\nFROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT id -- '{comment}'\nFROM users"
        assert offset_record == {13: 2}

    def test_adjacent_brackets(self):
        query = "SELECT {id}{name}{age} FROM users"
        result_sql, offset_record = replace_brackets_with_quotes(query)
        assert result_sql == "SELECT '{id}''{name}''{age}' FROM users"
        assert offset_record == {7: 2, 11: 2, 17: 2}
