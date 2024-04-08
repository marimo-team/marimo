# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Query by variable value
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        Evaluate a variable as the value to find.
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "first_name": ["Sarah", "John", "Kyle"],
            "last_name": ["Connor", "Connor", "Reese"],
        }
    )

    foo = "Connor"
    df.query("last_name == @foo")
    return df, foo, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
