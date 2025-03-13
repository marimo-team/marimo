# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Memory Optimization with Category Type""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame
    df = pd.DataFrame({
        'id': range(1000),
        'status': ['active', 'inactive', 'pending'] * 333 + ['active'],
        'category': ['A', 'B', 'C', 'D'] * 250
    })

    # Convert string columns to category
    # Refer: https://pandas.pydata.org/pandas-docs/stable/user_guide/categorical.html
    df['status'] = df['status'].astype('category')
    df['category'] = df['category'].astype('category')

    df.dtypes
    return df, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
