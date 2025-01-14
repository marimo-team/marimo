# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "duckdb==1.1.3",
#     "marimo[sql]==0.10.12",
#     "polars==1.19.0",
# ]
# ///

import marimo

__generated_with = "0.10.12"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import polars
    return (polars,)


@app.cell
def _(mo):
    mo.sql("as")
    return


if __name__ == "__main__":
    app.run()
