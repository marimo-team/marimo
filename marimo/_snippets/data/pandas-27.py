# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Multiple Column Aggregations""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B', 'B'],
        'numeric1': [10, 20, 30, 40, 50],
        'numeric2': [100, 200, 300, 400, 500],
        'text': ['x', 'y', 'z', 'x', 'y']
    })

    # Multiple aggregations
    agg_stats = df.groupby('group').agg(
        sum_numeric1=('numeric1', 'sum'),
        mean_numeric1=('numeric1', 'mean'),
        min_numeric2=('numeric2', 'min'),
        max_numeric2=('numeric2', 'max'),
        unique_texts=('text', 'nunique')
    ).reset_index()

    agg_stats
    return agg_stats, df, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
