# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.13"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def __(pd):
    df = pd.DataFrame(
        {
            "col$special": [1, 2, 3],
            "col@char": [4, 5, 6],
            'col"quote"': [7, 8, 9],
            "col'singlequote'": [10, 11, 12],
            "col<angles>": [13, 14, 15],
            "col{brace}": [16, 17, 18],
            "col[brackets]": [16, 17, 18],
            "col&and": [19, 20, 21],
            "col.period": [19, 20, 21],
            "col\\backslash": [19, 20, 21],
            "col\\backslash.period": [19, 20, 21],
        }
    )
    df
    return df,


@app.cell
def __(df, mo):
    mo.ui.table(df)
    return


@app.cell
def __(df, mo):
    mo.ui.dataframe(df)
    return


@app.cell
def __(df, mo):
    mo.ui.data_explorer(df)
    return


@app.cell
def __():
    import altair as alt
    return alt,


if __name__ == "__main__":
    app.run()
