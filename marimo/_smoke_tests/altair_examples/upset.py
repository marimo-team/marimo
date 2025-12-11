# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "altair-upset==0.4.0",
#     "pandas==2.3.2",
#     "pyarrow==22.0.0",
# ]
# ///

import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium", sql_output="polars")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import pyarrow
    from altair_upset import UpSetAltair
    return UpSetAltair, mo, pd


@app.cell
def _(pd):
    df = pd.DataFrame({"a": [1, 1, 1, 1, 1, 0], "b": [1, 1, 1, 0, 0, 0]})
    return (df,)


@app.cell
def _(UpSetAltair, df):
    chart = UpSetAltair(df, sorted(df.columns)).chart
    return (chart,)


@app.cell
def _(chart):
    chart
    return


@app.cell
def _(chart, mo):
    mo.ui.altair_chart(chart.copy())
    return


if __name__ == "__main__":
    app.run()
