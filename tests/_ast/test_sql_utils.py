# Copyright 2025 Marimo. All rights reserved.

import pytest

from marimo._ast.sql_utils import classify_sql_statement
from marimo._dependencies.dependencies import DependencyManager


@pytest.mark.skipif(
    not DependencyManager.sqlglot.has(), reason="Missing sqlglot"
)
class TestClassifySQLStatement:
    """Test cases for classify_sql_statement function."""

    def test_ddl_statements(self):
        """Test DDL (Data Definition Language) statements."""
        # CREATE statements
        assert classify_sql_statement("CREATE TABLE users (id INT)") == "DDL"
        assert (
            classify_sql_statement("CREATE INDEX idx_name ON table_name")
            == "DDL"
        )
        assert (
            classify_sql_statement(
                "CREATE VIEW my_view AS SELECT * FROM table"
            )
            == "DDL"
        )

        # DROP statements
        assert classify_sql_statement("DROP TABLE users") == "DDL"
        assert classify_sql_statement("DROP INDEX idx_name") == "DDL"
        assert classify_sql_statement("DROP VIEW my_view") == "DDL"

        # ALTER statements
        assert (
            classify_sql_statement(
                "ALTER TABLE users ADD COLUMN name VARCHAR(255)"
            )
            == "DDL"
        )
        assert (
            classify_sql_statement("ALTER TABLE users DROP COLUMN name")
            == "DDL"
        )
        # Modify, specific to MySQL
        assert (
            classify_sql_statement(
                "ALTER TABLE users MODIFY COLUMN name VARCHAR(100)", "mysql"
            )
            == "DDL"
        )

        # ATTACH statements (duckdb)
        assert (
            classify_sql_statement(
                "ATTACH DATABASE 'test.db' AS test", "duckdb"
            )
            == "DDL"
        )
        # DETACH statements (duckdb)
        assert (
            classify_sql_statement("DETACH DATABASE test", "duckdb") == "DDL"
        )

    def test_dml_statements(self):
        """Test DML (Data Manipulation Language) statements."""
        # INSERT statements
        assert (
            classify_sql_statement(
                "INSERT INTO users (name, age) VALUES ('John', 30)"
            )
            == "DML"
        )
        assert (
            classify_sql_statement(
                "INSERT INTO users SELECT * FROM temp_users"
            )
            == "DML"
        )

        # UPDATE statements
        assert (
            classify_sql_statement(
                "UPDATE users SET name = 'Jane' WHERE id = 1"
            )
            == "DML"
        )
        assert (
            classify_sql_statement("UPDATE users SET age = age + 1") == "DML"
        )

        # DELETE statements
        assert (
            classify_sql_statement("DELETE FROM users WHERE id = 1") == "DML"
        )
        assert classify_sql_statement("DELETE FROM users") == "DML"

    def test_dql_statements(self):
        """Test DQL (Data Query Language) statements."""
        # SELECT statements
        assert classify_sql_statement("SELECT * FROM users") == "DQL"
        assert (
            classify_sql_statement(
                "SELECT name, age FROM users WHERE age > 18"
            )
            == "DQL"
        )
        assert classify_sql_statement("SELECT COUNT(*) FROM users") == "DQL"
        assert (
            classify_sql_statement(
                "SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.user_id"
            )
            == "DQL"
        )

    @pytest.mark.skip(reason="DCL statements are not supported yet")
    def test_dcl_statements(self):
        """Test DCL (Data Control Language) statements."""
        assert classify_sql_statement("GRANT SELECT ON users TO john") == "DCL"
        assert (
            classify_sql_statement("REVOKE SELECT ON users FROM john") == "DCL"
        )
        assert classify_sql_statement("CREATE USER john") == "DCL"
        assert classify_sql_statement("DROP USER john") == "DCL"
        assert (
            classify_sql_statement(
                "ALTER USER john SET PASSWORD = 'new_password'"
            )
            == "DCL"
        )

    def test_case_insensitive(self):
        """Test that the function is case insensitive."""
        assert classify_sql_statement("create table users (id int)") == "DDL"
        assert classify_sql_statement("CREATE TABLE USERS (ID INT)") == "DDL"
        assert (
            classify_sql_statement("insert into users values (1, 'john')")
            == "DML"
        )
        assert (
            classify_sql_statement("INSERT INTO USERS VALUES (1, 'JOHN')")
            == "DML"
        )
        assert classify_sql_statement("select * from users") == "DQL"
        assert classify_sql_statement("SELECT * FROM USERS") == "DQL"

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        assert (
            classify_sql_statement("  CREATE TABLE users (id INT)  ") == "DDL"
        )
        assert (
            classify_sql_statement("\nINSERT INTO users VALUES (1)\n") == "DML"
        )
        assert classify_sql_statement("\tSELECT * FROM users\t") == "DQL"

    def test_dialect_specific_statements(self):
        """Test statements with specific dialects."""
        # PostgreSQL specific
        assert (
            classify_sql_statement(
                "CREATE TABLE users (id SERIAL)", "postgres"
            )
            == "DDL"
        )

        # MySQL specific
        assert (
            classify_sql_statement(
                "CREATE TABLE users (id INT AUTO_INCREMENT)", "mysql"
            )
            == "DDL"
        )

        # SQLite specific
        assert (
            classify_sql_statement(
                "CREATE TABLE users (id INTEGER PRIMARY KEY)", "sqlite"
            )
            == "DDL"
        )

        # DuckDB specific
        assert (
            classify_sql_statement("CREATE TABLE users (id INTEGER)", "duckdb")
            == "DDL"
        )

    def test_complex_statements(self):
        """Test complex SQL statements."""
        # Complex DML with subqueries
        complex_dml = """
        UPDATE users
        SET last_login = CURRENT_TIMESTAMP
        WHERE id IN (SELECT user_id FROM sessions WHERE active = true)
        """
        assert classify_sql_statement(complex_dml) == "DML"

        # Test CTEs
        complex_dql = """
        WITH active_users AS (
            SELECT * FROM users WHERE active = true
        )
        SELECT * FROM active_users
        """
        assert classify_sql_statement(complex_dql) == "DQL"

    def test_edge_cases(self):
        """Test edge cases and unusual inputs."""
        # Empty string
        assert classify_sql_statement("") == "unknown"

        # Whitespace only
        assert classify_sql_statement("   ") == "unknown"

        # Invalid SQL
        assert classify_sql_statement("INVALID SQL STATEMENT") == "unknown"
        assert (
            classify_sql_statement("SELECT * FROM") == "unknown"
        )  # Incomplete statement

        # SQL with comments
        assert (
            classify_sql_statement("-- This is a comment\nSELECT * FROM users")
            == "DQL"
        )
        assert (
            classify_sql_statement(
                "/* Multi-line comment */\nCREATE TABLE users (id INT)"
            )
            == "DDL"
        )

    def test_multiple_statements(self):
        """Test that the function handles the first statement in a batch."""
        # The function processes the first statement in the list
        assert (
            classify_sql_statement("SELECT * FROM users; SELECT * FROM posts")
            == "DQL"
        )
        assert (
            classify_sql_statement(
                "CREATE TABLE users; INSERT INTO users VALUES (1)"
            )
            == "DDL"
        )
