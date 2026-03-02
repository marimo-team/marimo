import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium", auto_download=["html"], sql_output="native")


@app.cell
def _():
    import marimo as mo
    import duckdb as db

    return db, mo


@app.cell
def _(db):
    connection = db.connect(":memory:")
    connection.sql(f"""
    CREATE OR REPLACE TABLE fake_data (
        id INTEGER,
        name VARCHAR,
        value INTEGER
    );

    INSERT INTO fake_data (id, name, value) VALUES
        (1, 'Alice', 100),
        (2, 'Bob', 150),
        (3, 'Charlie', 200),
        (4, 'David', 120),
        (5, 'Eve', 180);
    """)
    return (connection,)


@app.cell
def _(connection, mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE students (name VARCHAR, sid INTEGER);
        CREATE OR REPLACE TABLE exams (eid INTEGER, subject VARCHAR, sid INTEGER);
        INSERT INTO students VALUES ('Mark', 1), ('Joe', 2), ('Matthew', 3);
        INSERT INTO exams VALUES (10, 'Physics', 1), (20, 'Chemistry', 2), (30, 'Literature', 3);
        """,
        engine=connection,
    )
    return


@app.cell
def _(connection, mo):
    _df = mo.sql(
        f"""
        EXPLAIN ANALYZE
            SELECT name
            FROM students
            JOIN exams USING (sid)
            WHERE name LIKE 'Ma%';
        """,
        engine=connection,
    )
    return


@app.cell
def _(mo):
    import duckdb

    mo.plain_text(repr(duckdb.sql("explain select 1").pl()))
    return


@app.cell
def _(connection):
    connection.sql("explain select * from fake_data")
    return


@app.cell
def _(connection, mo):
    mo.md(f"""
    {connection.sql("explain select * from fake_data")}
    """)
    return


if __name__ == "__main__":
    app.run()
