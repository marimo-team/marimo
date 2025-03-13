# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Merge Operations""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrames
    df1 = pd.DataFrame({
        'id': [1, 2, 3, 4],
        'name': ['Alice', 'Bob', 'Charlie', 'David'],
        'dept': ['IT', 'HR', 'IT', 'Finance']
    })

    df2 = pd.DataFrame({
        'id': [1, 2, 3, 5],
        'salary': [50000, 60000, 75000, 65000],
        'bonus': [5000, 6000, 7500, 6500]
    })

    # Different types of joins
    merged_inner = pd.merge(df1, df2, on='id', how='inner')
    merged_left = pd.merge(df1, df2, on='id', how='left')

    merged_inner
    return df1, df2, merged_inner, merged_left, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
