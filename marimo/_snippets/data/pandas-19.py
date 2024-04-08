# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Ignore one Column
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "first_name": ["Sarah", "John", "Kyle", "Joe"],
            "last_name": ["Connor", "Connor", "Reese", "Bonnot"],
        }
    )

    df.loc[:, df.columns != "last_name"]
    return df, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
