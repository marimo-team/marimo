# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "marimo",
# ]
# ///
# Copyright 2025 Marimo. All rights reserved.

import marimo

__generated_with = "0.16.1"
app = marimo.App(width="medium")

with app.setup(hide_code=True):
    import marimo as mo
    import duckdb


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    # SQL Error Handling Smoke Test

    This notebook demonstrates marimo's SQL error handling capabilities across different types of SQL errors.
    Each section shows how marimo gracefully handles SQL errors with helpful error messages.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## Setup Test Data

    First, let's create some test data to work with.
    """
    )
    return


@app.cell
def _():
    # Create test data for our error examples
    test_setup = mo.sql(
        f"""
        CREATE OR REPLACE TABLE users (
            id INTEGER,
            name TEXT,
            email TEXT,
            age INTEGER
        )
        """
    )
    return (users,)


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        INSERT INTO users VALUES
        (1, 'Alice', 'alice@example.com', 25),
        (2, 'Bob', 'bob@example.com', 30),
        (3, 'Charlie', 'charlie@example.com', 35)
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 1. Table Not Found Errors

    DuckDB provides helpful suggestions when table names don't exist.
    """
    )
    return


@app.cell
def _(user):
    _df = mo.sql(
        f"""
        -- This will show "Table with name 'user' does not exist! Did you mean 'users'?"
        select * from user
        """
    )
    return


@app.cell
def _(user_table):
    _df = mo.sql(
        f"""
        -- Another table typo example - completely wrong name
        SELECT * FROM user_table
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 2. Column Not Found Errors

    Column reference errors with candidate suggestions.
    """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- This will show column not found with candidates
        -- Should be 'name' instead of 'user_name'
        SELECT user_name FROM users
        """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Another column error
        -- Should be 'name' instead of 'fullname'
        SELECT id, fullname, email FROM users
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 3. SQL Syntax Errors

    Various syntax errors with position information.
    """
    )
    return


@app.cell
def _():
    _df = mo.sql(
        f"""
        -- Missing FROM keyword (FRM instead of FROM)
        SELECT * FRM users
        """
    )
    return


@app.cell
def _():
    _df = mo.sql(
        f"""
        -- Malformed parentheses
        SELECT ( FROM users
        """
    )
    return


@app.cell
def _():
    _df = mo.sql(
        f"""
        -- Invalid WHERE clause - missing condition
        SELECT * FROM users WHERE
        """
    )
    return


@app.cell
def _():
    _df = mo.sql(
        f"""
        -- Multiple FROM clauses - invalid syntax
        SELECT * FROM users FROM users
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 4. Data Type Errors

    Type mismatch and conversion errors.
    """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Type conversion error - can't divide number by string
        SELECT age / 'invalid_string' FROM users
        """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- String comparison with number - type mismatch
        SELECT * FROM users WHERE name > 123
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 5. Function Errors

    Function call errors and argument mismatches.
    """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Invalid function name
        SELECT INVALID_FUNCTION(name) FROM users
        """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Wrong number of arguments for SUBSTRING
        -- Missing start position and length parameters
        SELECT SUBSTRING(name) FROM users
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 6. Aggregate Function Errors

    GROUP BY and aggregate function errors.
    """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Missing GROUP BY for non-aggregated column
        -- 'name' should be in GROUP BY when using COUNT(*)
        SELECT name, COUNT(*) FROM users
        """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Invalid HAVING without GROUP BY
        SELECT * FROM users HAVING COUNT(*) > 1
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 7. Complex Query Errors

    More complex SQL errors that might occur in real scenarios.
    """
    )
    return


@app.cell
def _(users):
    _df = mo.sql(
        f"""
        -- Subquery error - invalid_column doesn't exist
        SELECT * FROM users
        WHERE id IN (SELECT invalid_column FROM users)
        """
    )
    return


@app.cell
def _(nonexistent_table, users):
    _df = mo.sql(
        f"""
        -- JOIN error - nonexistent_table doesn't exist
        SELECT u.name, p.title
        FROM users u
        JOIN nonexistent_table p ON u.id = p.user_id
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 8. Very Long SQL Statements

    Testing error handling with long SQL that gets truncated.
    """
    )
    return


@app.cell
def _(nonexistent_table):
    _df = mo.sql(
        f"""
        -- Very long SELECT with many columns that don't exist
        -- This will show error message truncation
        SELECT {", ".join([f"col_{i}" for i in range(50)])}
        FROM nonexistent_table
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 9. SQL with Special Characters

    Testing error handling with special characters and edge cases.
    """
    )
    return


@app.cell
def _():
    _df = mo.sql(
        f"""
        -- SQL with quotes and special characters in table name
        SELECT * FROM 'table with spaces and quotes'
        """
    )
    return


@app.cell
def _(用户表):
    _df = mo.sql(
        f"""
        -- SQL with unicode characters in table name
        SELECT * FROM 用户表
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## 10. Successful Query for Comparison

    Here's a working query to show the contrast with error handling.
    """
    )
    return


@app.cell
def _(users):
    # This should work perfectly
    successful_query = mo.sql(
        f"""
        SELECT name, age, email
        FROM users
        WHERE age > 25
        ORDER BY age DESC
        """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    ## Summary

    This notebook demonstrates marimo's comprehensive SQL error handling:

    - **Clear Error Messages**: Specific, actionable error descriptions displayed in marimo's error UI
    - **Helpful Suggestions**: DuckDB's friendly error messages with "Did you mean?" suggestions
    - **Position Information**: Line and column details when available
    - **Statement Context**: Shows the problematic SQL statement in the structured error display
    - **Graceful Degradation**: Errors don't crash the notebook, they display as structured errors
    - **Truncation**: Long SQL statements are truncated for readability in error messages

    Each SQL cell above will display a structured error in marimo's error UI, showing how
    different types of SQL errors are handled gracefully with actionable feedback.
    """
    )
    return


if __name__ == "__main__":
    app.run()
