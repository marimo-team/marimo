# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Query by regexp (regular expression)
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

    df[df.last_name.str.match(".*onno.*")]
    return df, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
