# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Create from lists of values
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    last_names = ["Connor", "Connor", "Reese"]
    first_names = ["Sarah", "John", "Kyle"]
    df = pd.DataFrame(
        {
            "first_name": first_names,
            "last_name": last_names,
        }
    )
    df
    return df, first_names, last_names, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
