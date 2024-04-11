# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas: Create a TimeDelta using `unit`
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        From an integer.
        `unit` is a string, defaulting to `ns`. Possible values:

        """
    )
    return


@app.cell
def __():
    import pandas as pd

    pd.to_timedelta(1, unit="h")
    return (pd,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
