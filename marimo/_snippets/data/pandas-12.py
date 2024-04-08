# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas Timestamp: Convert string to Timestamp, using date only
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        I.e. Midnight on the given date.
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    pd.Timestamp("9/27/22").tz_localize("US/Pacific")
    return (pd,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
