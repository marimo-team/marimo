# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    import marimo as mo
    return mo, os


@app.cell
def _(mo, os):
    v = mo.ui.table(dict(os.environ))
    v
    return (v,)


@app.cell
def _(mo):
    mo.ui.table(
        {
            "a": 1,
            "b": 2,
        },
        format_mapping={
            "value": lambda x: x + 1,
        },
    )
    return


@app.cell
def _(v):
    v.value
    return


if __name__ == "__main__":
    app.run()
