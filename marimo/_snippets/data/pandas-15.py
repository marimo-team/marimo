# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas: Create a TimeDelta using available kwargs
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        Example keyworded args: {days, seconds, microseconds, milliseconds, minutes, hours, weeks}
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    pd.Timedelta(days=2)
    return (pd,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
