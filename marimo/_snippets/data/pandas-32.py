# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Boolean Indexing and Filtering""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame
    df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [25, 30, 35, 28, 22],
        'salary': [50000, 60000, 75000, 62000, 45000],
        'department': ['IT', 'HR', 'IT', 'Finance', 'HR']
    })

    # Multiple boolean conditions
    mask = (df['age'] > 25) & (df['salary'] > 60000)
    filtered_df = df[mask]

    filtered_df
    return df, filtered_df, mask, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
