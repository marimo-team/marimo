# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas: Replace NaN values in a Column
        """
    )
    return


@app.cell
def __():
    import numpy as np
    import pandas as pd

    df = pd.DataFrame(
        {
            "dogs": [5, 10, np.nan, 7],
        }
    )

    df["dogs"].replace(np.nan, 0, regex=True)
    return df, np, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
