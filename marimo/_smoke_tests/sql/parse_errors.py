import marimo

__generated_with = "0.16.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb
    import marimo as mo
    import json

    JSON_SERIALIZE_QUERY = "SELECT JSON_SERIALIZE_SQL(?, skip_null := true, skip_empty := true, skip_default := true, format := true)"


    def parse(query):
        return json.loads(
            duckdb.execute(JSON_SERIALIZE_QUERY, [query]).fetchone()[0]
        )
    return mo, parse


@app.cell
def _():
    queries = [
        "SELECT",
        "SELECT * FROM (SELECT 1 AS a, 2 AS b) AS subquery",
        "SELECT a, b FROM (SELECT 1 AS a, 2 AS b) AS subquery WHERE a = 1",
        "FROM subquery WHERE a = ",
        """
        SELECT a, b
        FROM foo
        WHERE a = 1;
        SELECT * FROM""",
    ]
    return (queries,)


@app.cell
def _(mo, queries):
    table = mo.ui.table(queries, selection="single")
    table
    return (table,)


@app.cell
def _(mo, parse, table):
    mo.stop(not table.value)
    parse(table.value[0])
    return


if __name__ == "__main__":
    app.run()
