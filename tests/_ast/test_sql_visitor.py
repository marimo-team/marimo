from __future__ import annotations

import ast
from textwrap import dedent

import pytest

from marimo._ast.sql_visitor import (
    SQLDefs,
    SQLVisitor,
    find_sql_defs,
)
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
    source_code = dedent(
        """
        a = db.sql('SELECT * FROM users', 'This should not be captured')
        b = db.sql('ALTER TABLE users ADD COLUMN name TEXT')
        c = db.sql('UPDATE users SET name = \\'Alice\\' WHERE id = 1')
        """
    )
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == [
        "SELECT * FROM users",
        "ALTER TABLE users ADD COLUMN name TEXT",
        "UPDATE users SET name = 'Alice' WHERE id = 1",
    ]


def test_sql_with_variable() -> None:
    source_code = dedent(
        """
      var = f"SELECT * FROM users WHERE name = {name}"
      db.sql(var)
    """
    )
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == []


@pytest.mark.skipif(not HAS_DUCKDB, reason="Missing DuckDB")
class TestFindCreatedTables:
    @staticmethod
    def test_find_sql_defs_simple() -> None:
        sql = "CREATE TABLE test_table (id INT, name VARCHAR(255));"
        assert find_sql_defs(sql) == SQLDefs(
            ["test_table"],
            [],
            [],
        )

        sql = "CREATE VIEW test_view (id INT, name VARCHAR(255));"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            ["test_view"],
            [],
        )

    @staticmethod
    def test_find_sql_defs_multiple() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE TABLE table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            [
                "table1",
                "table2",
            ],
            [],
            [],
        )

        sql = """
        CREATE VIEW table1 (id INT);
        CREATE VIEW table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [
                "table1",
                "table2",
            ],
            [],
        )

    @staticmethod
    def test_find_sql_defs_with_comments() -> None:
        sql = """
        CREATE TABLE
        -- This is a comment
        IF NOT EXISTS
        -- This is another comment
        table1 (id INT);
        -- This is a comment
        CREATE TABLE table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            [
                "table1",
                "table2",
            ],
            [],
            [],
        )

        sql = """
        CREATE VIEW
        -- This is a comment
        IF NOT EXISTS
        -- This is another comment
        table1 (id INT);
        -- This is a comment
        CREATE VIEW table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [
                "table1",
                "table2",
            ],
            [],
        )

    @staticmethod
    def test_find_sql_defs_with_or_replace() -> None:
        sql = "CREATE OR REPLACE TABLE test_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            ["test_table"],
            [],
            [],
        )

        sql = "CREATE OR REPLACE VIEW test_view (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            ["test_view"],
            [],
        )

    @staticmethod
    def test_find_sql_defs_temporary() -> None:
        sql = "CREATE TEMPORARY TABLE temp_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            ["temp_table"],
            [],
            [],
        )

        sql = "CREATE TEMPORARY VIEW temp_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            ["temp_table"],
            [],
        )

    @staticmethod
    def test_find_sql_defs_if_not_exists() -> None:
        sql = "CREATE TABLE IF NOT EXISTS new_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            ["new_table"],
            [],
            [],
        )

        sql = "CREATE VIEW IF NOT EXISTS new_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            ["new_table"],
            [],
        )

    @staticmethod
    def test_find_sql_defs_complex() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE OR REPLACE TEMPORARY TABLE IF NOT EXISTS table2 (name VARCHAR(255));
        CREATE TABLE table3 (date DATE);
        """  # noqa: E501
        assert find_sql_defs(sql) == SQLDefs(
            [
                "table1",
                "table2",
                "table3",
            ],
            [],
            [],
        )

        sql = """
        CREATE VIEW table1 (id INT);
        CREATE OR REPLACE TEMPORARY VIEW IF NOT EXISTS table2 (name VARCHAR(255));
        CREATE VIEW table3 (date DATE);
        """  # noqa: E501
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [
                "table1",
                "table2",
                "table3",
            ],
            [],
        )

    @staticmethod
    def test_find_sql_defs_no_create() -> None:
        sql = "SELECT * FROM existing_table;"
        assert find_sql_defs(sql) == SQLDefs([], [], [])

    @staticmethod
    def test_find_sql_defs_case_insensitive() -> None:
        sql = "create TABLE Test_Table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            ["Test_Table"],
            [],
            [],
        )

        sql = "create VIEW Test_Table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            ["Test_Table"],
            [],
        )

    @staticmethod
    @pytest.mark.parametrize(
        "query",
        [
            "",
            "   ",
            ";",
        ],
    )
    def test_find_sql_defs_empty_input(
        query: str,
    ) -> None:
        assert find_sql_defs(query) == SQLDefs(
            [],
            [],
            [],
        )

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
    def test_find_sql_defs_many_comments(
        query: str,
    ) -> None:
        assert find_sql_defs(query) == SQLDefs(
            ["my_table"],
            [],
            [],
        )

    @staticmethod
    def test_find_sql_defs_weird_names() -> None:
        sql = r"""
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

        CREATE TABLE 'single-quotes' (id INT);
        CREATE TABLE e'escaped\ntable' (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            [
                "my--table",
                "my_table_with_select",
                "my/*weird*/table",
                "with a space",
                "single-quotes",
                r"escaped\ntable",
            ],
            [],
            [],
        )

    @staticmethod
    def test_find_created_database() -> None:
        sql = "ATTACH 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [],
            ["Chinook"],
        )

        sql = "ATTACH 'Chinook.sqlite' AS my_db;"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [],
            ["my_db"],
        )
        sql = "ATTACH DATABASE 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [],
            ["Chinook"],
        )

        sql = "ATTACH DATABASE IF NOT EXISTS 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [],
            ["Chinook"],
        )

        sql = "ATTACH DATABASE IF NOT EXISTS 'Chinook.sqlite' AS my_db;"
        assert find_sql_defs(sql) == SQLDefs(
            [],
            [],
            ["my_db"],
        )


@pytest.mark.skipif(
    HAS_DUCKDB, reason="Test requires DuckDB to be unavailable"
)
def test_find_sql_defs_duckdb_not_available() -> None:
    assert find_sql_defs("CREATE TABLE test (id INT);") == SQLDefs([], [], [])
