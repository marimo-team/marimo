# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import pandas as pd
    return (pd,)


@app.cell
def _():
    import random


    def row(columns):
        return [
            "".join(random.choices("abcdefghikjlmnopqrstuvwxyz", k=8)),
            "".join(random.choices("abcdefghikjlmnopqrstuvwxyz", k=8)),
        ] + [random.randint(1000, 100000) for i in range(columns - 2)]
    return (row,)


@app.cell
def _(pd, row):
    df = pd.DataFrame([row(3) for _ in range(10)])
    return (df,)


@app.cell
def _():
    return


@app.cell
def _(df, mo):
    uidf = mo.ui.dataframe(df)
    uidf
    return


if __name__ == "__main__":
    app.run()
