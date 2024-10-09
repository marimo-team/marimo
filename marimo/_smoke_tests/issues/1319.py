# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.11"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import pandas as pd
    return pd,


@app.cell
def __():
    import random


    def row(columns):
        return [
            "".join(random.choices("abcdefghikjlmnopqrstuvwxyz", k=8)),
            "".join(random.choices("abcdefghikjlmnopqrstuvwxyz", k=8)),
        ] + [random.randint(1000, 100000) for i in range(columns - 2)]
    return random, row


@app.cell
def __(pd, row):
    df = pd.DataFrame([row(3) for _ in range(10)])
    return df,


@app.cell
def __():
    return


@app.cell
def __(df, mo):
    uidf = mo.ui.dataframe(df)
    uidf
    return uidf,


if __name__ == "__main__":
    app.run()
