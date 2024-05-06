# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.11"
app = marimo.App()


@app.cell
def __(pd):
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3], "c": [1, 2, 3]})
    renamed = df.rename({"b": "a"}, axis=1)
    renamed
    return df, renamed


@app.cell
def __(mo, renamed):
    mo.ui.table(renamed)
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


if __name__ == "__main__":
    app.run()
