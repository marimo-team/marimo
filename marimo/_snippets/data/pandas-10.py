# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Explode a column containing dictionary values into multiple columns
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        This code transforms or splits the dictionary column into many columns.

        E.g. The output DataFrame of this cell will have columns named [`date, letter, fruit, weather`].
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "date": ["2022-09-14", "2022-09-15", "2022-09-16"],
            "letter": ["A", "B", "C"],
            "dict": [
                {"fruit": "apple", "weather": "aces"},
                {"fruit": "banana", "weather": "bad"},
                {"fruit": "cantaloupe", "weather": "cloudy"},
            ],
        }
    )

    pd.concat([df.drop(["dict"], axis=1), df["dict"].apply(pd.Series)], axis=1)
    return df, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
