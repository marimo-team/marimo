import marimo

__generated_with = "0.18.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import narwhals as nw
    import polars as pl
    import pandas as pd
    return mo, nw, pd, pl


@app.cell
def _(pd, pl):
    data = data = {
        "A": ["foo", "foo", "foo", "foo", "foo", "bar", "bar", "bar", "bar"],
        "B": ["one", "one", "one", "two", "two", "one", "one", "two", "two"],
        "C": [
            "small",
            "large",
            "large",
            "small",
            "small",
            "large",
            "small",
            "small",
            "large",
        ],
        "D": [1, 2, 2, 3, 3, 4, 5, 6, 7],
        "E": [2, 4, 5, 5, 6, 6, 8, 9, 9],
        "F": ["a", "v", "v", "v", "a", "a", "v", "v", "a"],
    }

    pl_df = pl.DataFrame(data)
    pd_df = pd.DataFrame(data)
    return (pd_df,)


@app.cell
def _(mo, pd_df):
    mo.ui.dataframe(pd_df)
    return


@app.cell
def _():
    return


@app.cell
def _(nw, pd_df):
    nw.from_native(pd_df).group_by("A", "B", "C", "F").agg(
        nw.col("D").count()
    ).to_native()
    return


@app.cell
def _(nw, pd_df):
    nw.from_native(pd_df).pivot(
        on=["A", "F"],
        index=["B", "C"],
        values=["D", "E"],
        aggregate_function="count",
    ).select(nw.all().fill_null(0))
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
