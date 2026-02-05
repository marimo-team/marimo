# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        """
    # Bug 852

    Explanation: The table was rendering incorrectly due to javascript number precision.
    """
    )
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def _(pd):
    df = pd.DataFrame({"data": [912312851340981241284, None, "abc"]})
    df
    return (df,)


@app.cell
def _(df, mo):
    table = mo.ui.table(df)
    table
    return


if __name__ == "__main__":
    app.run()
