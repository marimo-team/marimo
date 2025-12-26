# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(pd):
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3], "c": [1, 2, 3]})
    renamed = df.rename({"b": "a"}, axis=1)
    renamed
    return (renamed,)


@app.cell
def _(mo, renamed):
    mo.ui.table(renamed)
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


if __name__ == "__main__":
    app.run()
