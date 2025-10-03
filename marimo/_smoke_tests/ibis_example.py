# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.16.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import ibis
    return ibis, mo


@app.cell
def _(ibis):
    df = ibis.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv",
        table_name="penguins",
    )
    df
    return (df,)


@app.cell
def _(df, mo):
    # Print Ibis data in a pretty table
    mo.ui.table(df)
    return


@app.cell
def _(df):
    df.to_polars()
    return


@app.cell
def _(df):
    # Transform using the python API
    _res = df.group_by("species", "island").agg(count=df.count()).order_by("count")
    df.to_polars()
    return


@app.cell
def _(df):
    # Transform using SQL
    _res = df.sql(
        "SELECT species, island, count(*) AS count FROM penguins GROUP BY 1, 2"
    )
    _res.to_polars()
    return


@app.cell
def _(df, mo):
    # Transform using the ui.dataframe GUI
    mo.ui.dataframe(df)
    return


@app.cell
def _(ibis):
    # Unnest
    ibis.memtable(
        {
            "x": [[0, 1, 2], [], [], [3, 4]],
            "y": [["a", "b", "c"], [], [], ["d", "e"]],
        }
    ).unnest("x").to_polars()
    return


@app.cell
def _(ibis):
    # Unpack
    ibis.memtable({"A": [{"foo": 1, "bar": "hello"}], "B": [1]}).unpack(
        "A"
    ).to_polars()
    return


if __name__ == "__main__":
    app.run()
