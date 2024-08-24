# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")


@app.cell
def __():
    import os
    import marimo as mo
    return mo, os


@app.cell
def __(mo, os):
    v = mo.ui.table(dict(os.environ))
    v
    return v,


@app.cell
def __(mo):
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
def __(v):
    v.value
    return


if __name__ == "__main__":
    app.run()
