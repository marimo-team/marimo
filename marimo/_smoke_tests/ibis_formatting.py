# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ibis-framework[duckdb,polars]==10.8.0",
#     "marimo",
#     "polars==1.32.0",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import ibis
    import polars as pl
    import marimo as mo
    return ibis, pl


@app.cell
def _():
    from ibis import _
    from datetime import datetime
    return


@app.cell
def _():
    test_data = {
        "str": ["a", "c", "hello"],
        "num": [1, 2, 3],
        "list": [["a", "b"], ["c"], []],
        "struct": [{"a": 0}, {"a": 1}, {"a": 2}],
        "floats": [1.1, 2.2, None],
    }
    return (test_data,)


@app.cell
def _(ibis, test_data):
    t = ibis.memtable(test_data)
    return (t,)


@app.cell
def _(ibis, t):
    # Table - lazy mode: Expression + SQL tabs
    ibis.options.interactive = False

    t
    return


@app.cell
def _(ibis, t):
    # Column - lazy mode: Expression + SQL tabs
    ibis.options.interactive = False

    t.struct
    return


@app.cell
def _(ibis, t):
    # Scalar - lazy mode: Expression + SQL tabs
    ibis.options.interactive = False

    t.floats.min()
    return


@app.cell
def _(ibis, t):
    # Table - interactive mode: table widget
    ibis.options.interactive = True

    t
    return


@app.cell
def _(ibis, t):
    # Column - interactive mode: table widget
    ibis.options.interactive = True

    t.struct
    return


@app.cell
def _(ibis, t):
    # Array scalar - interactive mode: JSON output
    ibis.options.interactive = True

    t.list.first()
    return


@app.cell
def _(ibis, t):
    # Scalar - interactive mode: plain text
    ibis.options.interactive = True

    t.floats.min()
    return


@app.cell
def _(ibis):
    # Unbound tables

    t1 = ibis.table(
        dict(value1="float", key1="string", key2="string"), name="table1"
    )
    t2 = ibis.table(
        dict(value2="float", key3="string", key4="string"), name="table2"
    )

    joined = t1.left_join(t2, t1.key1 == t2.key3)
    return (joined,)


@app.cell
def _(ibis, joined):
    # Unbound table: Expression + SQL tabs
    ibis.options.interactive = False

    joined
    return


@app.cell
def _(ibis, joined):
    # Unbound table - interactive mode: Expression + SQL tabs
    ibis.options.interactive = True

    joined
    return


@app.cell
def _(pl):
    lazy_frame = pl.LazyFrame(
        {"name": ["Jimmy", "Keith"], "band": ["Led Zeppelin", "Stones"]}
    )
    return (lazy_frame,)


@app.cell
def _(ibis, lazy_frame):
    pl_connection = ibis.polars.connect(tables={"band_members": lazy_frame})
    return (pl_connection,)


@app.cell
def _(ibis, pl_connection):
    # Polars table - lazy mode: Expression + SQL tabs (SQL shows "Backend doesn't support SQL")
    ibis.options.interactive = False

    pl_connection.table("band_members")
    return


@app.cell
def _(ibis, pl_connection):
    # Polars scalar - lazy mode: Expression + SQL tabs (SQL shows "Backend doesn't support SQL")
    ibis.options.interactive = False

    pl_connection.table("band_members").name.first()
    return


@app.cell
def _(ibis, pl_connection):
    # Polars table - interactive mode: table widget
    ibis.options.interactive = True

    pl_connection.table("band_members")
    return


@app.cell
def _(ibis, pl_connection):
    # Polars scalar - interactive mode: plain text
    ibis.options.interactive = True

    pl_connection.table("band_members").name.first()
    return


@app.cell
def _(ibis, t):
    duckb_con = ibis.duckdb.connect()
    duckdb_table = duckb_con.create_table("test", t, overwrite=True)
    return (duckdb_table,)


@app.cell
def _(duckdb_table, ibis):
    # DuckDB table - lazy mode: Expression + SQL tabs
    ibis.options.interactive = False

    duckdb_table
    return


@app.cell
def _(duckdb_table, ibis):
    # DuckDB table - interactive mode: table widget
    ibis.options.interactive = True

    duckdb_table
    return


if __name__ == "__main__":
    app.run()
