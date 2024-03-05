# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """
    # Bug 852

    Explanation: The table was rendering incorrectly due to javascript number precision.
    """
    )
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def __(pd):
    df = pd.DataFrame({"data": [912312851340981241284, None, "abc"]})
    df
    return df,


@app.cell
def __(df, mo):
    table = mo.ui.table(df)
    table
    return table,


if __name__ == "__main__":
    app.run()
