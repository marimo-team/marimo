import marimo

__generated_with = "0.13.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import sqlite3
    return (sqlite3,)


@app.cell
def _(sqlite3):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value REAL
        )
    """)
    conn.execute("""
        INSERT INTO test (name, value) VALUES
        ('a', 1.0),
        ('b', 2.0),
        ('c', 3.0)
    """)
    return (conn,)



@app.cell
def _(conn, mo, test):
    _df = mo.sql(
        f"""
        select * FROM test
        """,
        engine=conn
    )
    return


if __name__ == "__main__":
    app.run()
