# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Rename multiple Columns
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "Year": [2016, 2015, 2014, 2013, 2012],
            "Top Animal": ["Giant panda", "Chicken", "Pig", "Turkey", "Dog"],
        }
    )

    df.rename(
        columns={
            "Year": "Calendar Year",
            "Top Animal": "Favorite Animal",
        },
        inplace=True,
    )
    df
    return df, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
