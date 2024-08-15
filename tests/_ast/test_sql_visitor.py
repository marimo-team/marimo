from __future__ import annotations

import ast
from textwrap import dedent

import pytest

from marimo._ast.sql_visitor import SQLVisitor, find_created_tables
from marimo._dependencies.dependencies import DependencyManager

HAS_DUCKDB = DependencyManager.duckdb.has()


def test_execute_with_string_literal() -> None:
    source_code = "db.execute('SELECT * FROM users')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users"]


def test_sql_with_string_literal() -> None:
    source_code = "db.sql('UPDATE users SET name = \\'Alice\\' WHERE id = 1')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == [
        "UPDATE users SET name = 'Alice' WHERE id = 1"
    ]


def test_execute_with_f_string() -> None:
    source_code = 'db.execute(f"SELECT * FROM users WHERE name = {name}")'
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users WHERE name = '_'"]


def test_no_sql_calls() -> None:
    source_code = "print('Hello, world!')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == []


def test_sql_with_multiple_arguments() -> None:
    source_code = (
        "db.sql('SELECT * FROM users', 'This should not be captured')"
    )
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users"]


def test_multiple_sql_calls() -> None:
    source_code = dedent("""
        a = db.sql('SELECT * FROM users', 'This should not be captured')
        b = db.sql('ALTER TABLE users ADD COLUMN name TEXT')
        c = db.sql('UPDATE users SET name = \\'Alice\\' WHERE id = 1')
        """)
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == [
        "SELECT * FROM users",
        "ALTER TABLE users ADD COLUMN name TEXT",
        "UPDATE users SET name = 'Alice' WHERE id = 1",
    ]


def test_sql_with_variable() -> None:
    source_code = dedent("""
      var = f"SELECT * FROM users WHERE name = {name}"
      db.sql(var)
    """)
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == []


@pytest.mark.skipif(not HAS_DUCKDB, reason="Missing DuckDB")
class TestFindCreatedTables:
    @staticmethod
    def test_find_created_tables_simple() -> None:
        sql = "CREATE TABLE test_table (id INT, name VARCHAR(255));"
        assert find_created_tables(sql) == ["test_table"]

    @staticmethod
    def test_find_created_tables_multiple() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE TABLE table2 (name VARCHAR(255));
        """
        assert find_created_tables(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_created_tables_with_comments() -> None:
        sql = """
        CREATE TABLE
        -- This is a comment
        IF NOT EXISTS
        -- This is another comment
        table1 (id INT);
        -- This is a comment
        CREATE TABLE table2 (name VARCHAR(255));
        """
        assert find_created_tables(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_created_tables_with_or_replace() -> None:
        sql = "CREATE OR REPLACE TABLE test_table (id INT);"
        assert find_created_tables(sql) == ["test_table"]

    @staticmethod
    def test_find_created_tables_temporary() -> None:
        sql = "CREATE TEMPORARY TABLE temp_table (id INT);"
        assert find_created_tables(sql) == ["temp_table"]

    @staticmethod
    def test_find_created_tables_if_not_exists() -> None:
        sql = "CREATE TABLE IF NOT EXISTS new_table (id INT);"
        assert find_created_tables(sql) == ["new_table"]

    @staticmethod
    def test_find_created_tables_complex() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE OR REPLACE TEMPORARY TABLE IF NOT EXISTS table2 (name VARCHAR(255));
        CREATE TABLE table3 (date DATE);
        """  # noqa: E501
        assert find_created_tables(sql) == ["table1", "table2", "table3"]

    @staticmethod
    def test_find_created_tables_no_create() -> None:
        sql = "SELECT * FROM existing_table;"
        assert find_created_tables(sql) == []

    @staticmethod
    def test_find_created_tables_case_insensitive() -> None:
        sql = "create TABLE Test_Table (id INT);"
        assert find_created_tables(sql) == ["Test_Table"]

    @staticmethod
    @pytest.mark.parametrize(
        "query",
        [
            "",
            "   ",
            ";",
        ],
    )
    def test_find_created_tables_empty_input(query: str) -> None:
        assert find_created_tables(query) == []

    @staticmethod
    @pytest.mark.parametrize(
        "query",
        [
            """
            -- This is a comment
            CREATE TABLE my_table (
                my_column INT, -- Inline comment
                my_other_column INT
            )
            """,
            """
            /* Multi-line
            comment */
            CREATE OR REPLACE TABLE my_table (
                my_column INT,
                my_other_column INT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS my_table
            -- Comment before AS
            AS
            /* Comment
            before SELECT */
            SELECT * FROM read_csv()
            """,
            """
            CREATE TEMPORARY TABLE my_table AS
            -- Comment in the middle
            SELECT * FROM existing_table
            """,
            """
            -- Comment at the start
            CREATE OR REPLACE TEMP TABLE IF NOT EXISTS my_table (
                id INT, -- Comment after column
                name VARCHAR
            ) -- Comment at the end
            """,
        ],
    )
    def test_find_created_tables_many_comments(query: str) -> None:
        assert find_created_tables(query) == ["my_table"]

    @staticmethod
    def test_find_created_tables_weird_names() -> None:
        sql = """
        CREATE TABLE "my--table" (
            "column/*with*/comment" INT,
            "another--column" VARCHAR
        );

        CREATE TABLE my_table_with_select AS
        SELECT *
        FROM (
            VALUES
            ('a', 1),
            ('b', 2)
        ) AS t("col--1", "col--2");

        CREATE TABLE "my/*weird*/table" (id INT);

        CREATE TABLE "with a space" (id INT);
        """
        assert find_created_tables(sql) == [
            "my--table",
            "my_table_with_select",
            "my/*weird*/table",
            "with a space",
        ]


@pytest.mark.skipif(
    HAS_DUCKDB, reason="Test requires DuckDB to be unavailable"
)
def test_find_created_tables_duckdb_not_available() -> None:
    assert find_created_tables("CREATE TABLE test (id INT);") is None
