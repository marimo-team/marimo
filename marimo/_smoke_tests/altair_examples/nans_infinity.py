import marimo

__generated_with = "0.12.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import polars as pl

    import marimo as mo

    return mo, pd, pl


@app.cell
def _(mo, pd, pl):
    data = {"x": [1, 2, 3], "y": [float("-inf"), float("nan"), float("inf")]}
    pandas_df = pd.DataFrame(data).plot.line(x="x", y="y")
    polars_df = pl.DataFrame(data).plot.line(x="x", y="y")

    md = mo.md("### Invalid JSON values should be sanitized for charting")
    mo.vstack([md, polars_df, pandas_df], heights=[20, 50, 50])
    return data, md, pandas_df, polars_df


if __name__ == "__main__":
    app.run()
