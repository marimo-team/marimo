from __future__ import annotations

import ast
from textwrap import dedent

import pytest

from marimo._ast.sql_visitor import (
    SQLDefs,
    SQLVisitor,
    find_sql_defs,
    find_sql_refs,
)
from marimo._dependencies.dependencies import DependencyManager

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLGLOT = DependencyManager.sqlglot.has()


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
    assert visitor.get_sqls() == ["SELECT * FROM users WHERE name = null"]


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
class TestFindSQLDefs:
    @staticmethod
    def test_find_sql_defs_simple() -> None:
        sql = "CREATE TABLE test_table (id INT, name VARCHAR(255));"
        assert find_sql_defs(sql) == SQLDefs(
            tables=["test_table"],
        )

        sql = "CREATE VIEW test_view (id INT, name VARCHAR(255));"
        assert find_sql_defs(sql) == SQLDefs(
            views=["test_view"],
        )

    @staticmethod
    def test_find_sql_defs_multiple() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE TABLE table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=[
                "table1",
                "table2",
            ],
        )

        sql = """
        CREATE VIEW table1 (id INT);
        CREATE VIEW table2 (name VARCHAR(255));
        """
        assert find_sql_defs(sql) == SQLDefs(
            views=[
                "table1",
                "table2",
            ],
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
            tables=[
                "table1",
                "table2",
            ],
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
            views=[
                "table1",
                "table2",
            ],
        )

    @staticmethod
    def test_find_sql_defs_with_or_replace() -> None:
        sql = "CREATE OR REPLACE TABLE test_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            tables=["test_table"],
        )

        sql = "CREATE OR REPLACE VIEW test_view (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            views=["test_view"],
        )

    @staticmethod
    def test_find_sql_defs_temporary() -> None:
        sql = "CREATE TEMPORARY TABLE temp_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            tables=["temp_table"],
        )

        sql = "CREATE TEMPORARY VIEW temp_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            views=["temp_table"],
        )

    @staticmethod
    def test_find_sql_defs_if_not_exists() -> None:
        sql = "CREATE TABLE IF NOT EXISTS new_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            tables=["new_table"],
        )

        sql = "CREATE VIEW IF NOT EXISTS new_table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            views=["new_table"],
        )

    @staticmethod
    def test_find_sql_defs_complex() -> None:
        sql = """
        CREATE TABLE table1 (id INT);
        CREATE OR REPLACE TEMPORARY TABLE IF NOT EXISTS table2 (name VARCHAR(255));
        CREATE TABLE table3 (date DATE);
        """  # noqa: E501
        assert find_sql_defs(sql) == SQLDefs(
            tables=[
                "table1",
                "table2",
                "table3",
            ],
        )

        sql = """
        CREATE VIEW table1 (id INT);
        CREATE OR REPLACE TEMPORARY VIEW IF NOT EXISTS table2 (name VARCHAR(255));
        CREATE VIEW table3 (date DATE);
        """  # noqa: E501
        assert find_sql_defs(sql) == SQLDefs(
            views=[
                "table1",
                "table2",
                "table3",
            ],
        )

    @staticmethod
    def test_find_sql_defs_no_create() -> None:
        sql = "SELECT * FROM existing_table;"
        assert find_sql_defs(sql) == SQLDefs()

    @staticmethod
    def test_find_sql_defs_case_insensitive() -> None:
        sql = "create TABLE Test_Table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            tables=["Test_Table"],
        )

        sql = "create VIEW Test_Table (id INT);"
        assert find_sql_defs(sql) == SQLDefs(
            views=["Test_Table"],
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
        assert find_sql_defs(query) == SQLDefs()

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
            tables=["my_table"],
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
            tables=[
                "my--table",
                "my_table_with_select",
                "my/*weird*/table",
                "with a space",
                "single-quotes",
                r"escaped\ntable",
            ],
        )

    @staticmethod
    def test_find_created_database() -> None:
        sql = "ATTACH 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["Chinook"],
        )

        sql = "ATTACH 'Chinook.sqlite' AS my_db;"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["my_db"],
        )
        sql = "ATTACH DATABASE 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["Chinook"],
        )

        sql = "ATTACH DATABASE IF NOT EXISTS 'Chinook.sqlite';"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["Chinook"],
        )

        sql = "ATTACH DATABASE IF NOT EXISTS 'Chinook.sqlite' AS my_db;"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["my_db"],
        )

    @staticmethod
    def test_find_sql_defs_attach_with_colon() -> None:
        sql = "ATTACH 'md:my_db'"
        assert find_sql_defs(sql) == SQLDefs(
            catalogs=["my_db"],
        )

    @staticmethod
    def test_find_sql_defs_with_catalog() -> None:
        sql = """
        CREATE TABLE my_catalog.my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
            reffed_catalogs=["my_catalog"],
        )

    @staticmethod
    def test_find_sql_defs_create_or_replace_with_catalog() -> None:
        sql = """
        CREATE OR REPLACE TABLE my_db.my_table as (SELECT 42);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
            reffed_catalogs=["my_db"],
        )

    @staticmethod
    def test_find_sql_defs_with_catalog_and_schema() -> None:
        sql = """
        CREATE TABLE my_catalog.my_schema.my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
            reffed_catalogs=["my_catalog"],
            reffed_schemas=["my_schema"],
        )

    @staticmethod
    def test_find_sql_defs_with_catalog_and_main() -> None:
        sql = """
        CREATE TABLE my_catalog.main.my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
            reffed_catalogs=["my_catalog"],
            reffed_schemas=[],  # main not included, since that is the default
        )

    @staticmethod
    def test_find_sql_defs_create_schema() -> None:
        sql = """
        CREATE SCHEMA my_catalog.my_schema;
        """
        assert find_sql_defs(sql) == SQLDefs(
            schemas=["my_schema"],
            reffed_catalogs=["my_catalog"],
        )

    @staticmethod
    def test_find_sql_defs_with_in_memory_catalog_and_schema() -> None:
        sql = """
        CREATE TABLE memory.main.my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
        )

    @staticmethod
    def test_find_sql_defs_with_in_memory_catalog() -> None:
        sql = """
        CREATE TABLE memory.my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
        )

    @staticmethod
    def test_find_sql_defs_with_temp_table() -> None:
        sql = """
        CREATE TEMP TABLE my_temp_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_temp_table"],
        )

    @staticmethod
    def test_find_sql_defs_with_if_not_exists() -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS my_table (id INT);
        """
        assert find_sql_defs(sql) == SQLDefs(
            tables=["my_table"],
        )


@pytest.mark.skipif(
    HAS_DUCKDB, reason="Test requires DuckDB to be unavailable"
)
def test_find_sql_defs_duckdb_not_available() -> None:
    assert find_sql_defs("CREATE TABLE test (id INT);") == SQLDefs()


@pytest.mark.skipif(not HAS_SQLGLOT, reason="Missing sqlglot")
class TestFindSQLRefs:
    @staticmethod
    def test_find_sql_refs_simple() -> None:
        sql = "SELECT * FROM test_table;"
        assert find_sql_refs(sql) == ["test_table"]

    @staticmethod
    def test_find_sql_refs_multiple() -> None:
        sql = """
        SELECT * FROM table1;
        SELECT * FROM table2;
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_without_duplicates() -> None:
        sql = """
        SELECT * FROM table1;
        SELECT * FROM table2;
        SELECT * FROM table1;
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_with_function() -> None:
        sql = """
        SELECT *, embedding(text) as text_embedding
        FROM prompts;
        """
        assert find_sql_refs(sql) == ["prompts"]

    @staticmethod
    def test_find_sql_refs_with_schema() -> None:
        sql = "SELECT * FROM my_schema.my_table;"
        assert find_sql_refs(sql) == ["my_schema", "my_table"]

    @staticmethod
    def test_find_sql_refs_with_catalog() -> None:
        # Skip the schema if it's coming from a catalog
        sql = "SELECT * FROM my_catalog.my_schema.my_table;"
        assert find_sql_refs(sql) == ["my_catalog", "my_table"]

    @staticmethod
    def test_find_sql_refs_skip_memory_main() -> None:
        # This is the default in-memory catalog and schema
        # and we don't want to include them in the references
        sql = "SELECT * FROM memory.main.my_table;"
        assert find_sql_refs(sql) == ["my_table"]

    @staticmethod
    def test_find_sql_refs_with_join() -> None:
        sql = """
        SELECT * FROM table1
        JOIN table2 ON table1.id = table2.id;
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_with_subquery() -> None:
        sql = """
        SELECT * FROM (
            SELECT * FROM inner_table
        ) t;
        """
        assert find_sql_refs(sql) == ["inner_table"]

    @staticmethod
    def test_find_sql_refs_with_cte() -> None:
        sql = """
        WITH cte AS (
            SELECT * FROM source_table
        )
        SELECT * FROM cte;
        """
        assert find_sql_refs(sql) == ["source_table"]

    @staticmethod
    def test_find_sql_refs_with_union() -> None:
        sql = """
        SELECT * FROM table1
        UNION
        SELECT * FROM table2;
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_with_quoted_names() -> None:
        sql = """
        SELECT * FROM "My Table"
        JOIN "Weird.Name" ON "My Table".id = "Weird.Name".id;
        """
        assert find_sql_refs(sql) == ["My Table", "Weird.Name"]

    @staticmethod
    def test_find_sql_refs_with_multiple_ctes() -> None:
        sql = """
        WITH
            cte1 AS (SELECT * FROM table1),
            cte2 AS (SELECT * FROM table2),
            cte3 AS (SELECT * FROM cte1 JOIN cte2)
        SELECT * FROM cte3;
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_with_nested_joins() -> None:
        sql = """
        SELECT * FROM t1
        JOIN (t2 JOIN t3 ON t2.id = t3.id)
        ON t1.id = t2.id;
        """
        assert find_sql_refs(sql) == ["t1", "t2", "t3"]

    @staticmethod
    def test_find_sql_refs_with_lateral_join() -> None:
        sql = """
        SELECT * FROM employees,
        LATERAL (SELECT * FROM departments WHERE departments.id = employees.dept_id) dept;
        """
        assert find_sql_refs(sql) == ["departments", "employees"]

    @staticmethod
    def test_find_sql_refs_with_schema_switching() -> None:
        sql = """
        SELECT * FROM schema1.table1
        JOIN schema2.table2 ON schema1.table1.id = schema2.table2.id;
        """
        assert find_sql_refs(sql) == ["schema1", "table1", "schema2", "table2"]

    @staticmethod
    def test_find_sql_refs_with_complex_subqueries() -> None:
        sql = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM deeply.nested.table
            ) t1
            JOIN another_table
        ) t2;
        """
        assert find_sql_refs(sql) == ["deeply", "table", "another_table"]

    @staticmethod
    def test_find_sql_refs_nested_intersect() -> None:
        sql = """
        SELECT * FROM table1
        WHERE id IN (
            SELECT id FROM table2
            UNION
            SELECT id FROM table3
            INTERSECT
            SELECT id FROM table4
        );
        """
        assert find_sql_refs(sql) == ["table2", "table3", "table4", "table1"]

    @staticmethod
    def test_find_sql_refs_with_alias() -> None:
        sql = "SELECT * FROM employees AS e;"
        assert find_sql_refs(sql) == ["employees"]

    @staticmethod
    def test_find_sql_refs_comment() -> None:
        sql = """
        -- comment
        SELECT * FROM table1;
        -- comment
        """
        assert find_sql_refs(sql) == ["table1"]

    @staticmethod
    def test_find_sql_refs_ddl() -> None:
        # we are not referencing any table hence no refs
        sql = "CREATE TABLE t1 (id int);"
        assert find_sql_refs(sql) == []

    @staticmethod
    def test_find_sql_refs_ddl_with_reference() -> None:
        sql = """
        CREATE TABLE table2 AS
        WITH x AS (
            SELECT * from table1
        )
        SELECT * FROM x;
        """
        assert find_sql_refs(sql) == ["table1"]

    @staticmethod
    def test_find_sql_refs_update() -> None:
        sql = "UPDATE my_schema.table1 SET id = 1"
        assert find_sql_refs(sql) == ["my_schema", "table1"]

    @staticmethod
    def test_find_sql_refs_insert() -> None:
        sql = "INSERT INTO my_schema.table1 (id INT) VALUES (1,2);"
        assert find_sql_refs(sql) == ["my_schema", "table1"]

    @staticmethod
    def test_find_sql_refs_delete() -> None:
        sql = "DELETE FROM my_schema.table1 WHERE true;"
        assert find_sql_refs(sql) == ["my_schema", "table1"]

    @staticmethod
    def test_find_sql_refs_multi_dml() -> None:
        sql = """
        INSERT INTO table1 (id INT) VALUES (1,2);
        DELETE FROM table2 WHERE true;
        UPDATE table3 SET id = 1;
        """
        assert find_sql_refs(sql) == ["table1", "table2", "table3"]

    @staticmethod
    def test_find_sql_refs_multiple_selects_in_update() -> None:
        sql = """
        UPDATE schema1.table1
        SET table1.column1 = (
            SELECT table2.column2 FROM schema2.table2
        ),
        table1.column3 = (
            SELECT table3.column3 FROM table3
        )
        WHERE EXISTS (
            SELECT 1 FROM table2
        )
        AND table1.column4 IN (
            SELECT table4.column4 FROM table4
        );
        """
        assert find_sql_refs(sql) == [
            "schema1",
            "table1",
            "schema2",
            "table2",
            "table3",
            "table4",
        ]

    @staticmethod
    def test_find_sql_refs_select_in_insert() -> None:
        sql = """
        INSERT INTO table1 (column1, column2)
        SELECT column1, column2 FROM table2
        WHERE column3 = 'value';
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_select_in_delete() -> None:
        sql = """
        DELETE FROM table1
        WHERE column1 IN (
            SELECT column1 FROM table2
            WHERE column2 = 'value'
        );
        """
        assert find_sql_refs(sql) == ["table1", "table2"]

    @staticmethod
    def test_find_sql_refs_invalid_sql() -> None:
        sql = "SELECT * FROM"
        assert find_sql_refs(sql) == []

    @staticmethod
    def test_dml_with_subquery() -> None:
        sql = """
        insert into table1 (column1) select distinct column1 from table2 order by random();
        update table3 set column1=(select column2 from table1 t where t.column1=table3.column1);
        """
        assert find_sql_refs(sql) == [
            "table1",
            "table2",
            "table3",
        ]
