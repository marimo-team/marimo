# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars>=1.9.0",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


@app.cell
def _(pl):
    lists = pl.DataFrame(
        {"values": [[1, 2], [], None], "other": [[3, 4], [], None], "id": [0, 1, 2]}
    )
    return (lists,)


@app.cell
def _(mo):
    mo.md("""
    Explode **values**, then repeat with **values** and **other** together.
    Both eager and lazy dataframes should retain four rows, including the
    empty-list and null rows. Run the generated Python code and compare it
    with the dataframe UI, including the **id** column.
    """)
    return


@app.cell
def _(lists, mo):
    eager = mo.ui.dataframe(lists)
    eager
    return (eager,)


@app.cell
def _(eager):
    eager.value
    return


@app.cell
def _(lists, mo):
    lazy = mo.ui.dataframe(lists.lazy())
    lazy
    return (lazy,)


@app.cell
def _(lazy):
    lazy.value
    return


if __name__ == "__main__":
    app.run()
