# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Intersect Indexes
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    terminator_df = pd.DataFrame(
        {
            "first_name": ["Sarah", "John", "Kyle"],
            "last_name": ["Connor", "Connor", "Reese"],
        }
    )
    terminator_df.set_index("first_name", inplace=True)

    buckaroo_df = pd.DataFrame(
        {
            "first_name": ["John", "John", "Buckaroo"],
            "last_name": ["Parker", "Whorfin", "Banzai"],
        }
    )
    buckaroo_df.set_index("first_name", inplace=True)

    terminator_df.index.intersection(buckaroo_df.index).shape
    return buckaroo_df, pd, terminator_df


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
