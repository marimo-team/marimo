# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.15"
app = marimo.App(width="medium")


@app.cell
def __():
    import os
    import marimo as mo
    return mo, os


@app.cell
def __(mo):
    _size = 10
    mo.ui.table([x for x in range(_size)], page_size=_size, selection=None)
    return


@app.cell
def __(mo):
    _size = 20
    mo.ui.table(
        [{"one": x, "two": x * 3} for x in range(0, _size)],
        page_size=_size,
        heatmap=True,
        selection=None,
    )
    return


if __name__ == "__main__":
    app.run()
