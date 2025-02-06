# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Advanced Groupby Operations""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B', 'C'],
        'value1': [10, 20, 30, 40, 50],
        'value2': [1, 2, 3, 4, 5]
    })

    # Multiple groupby operations
    grouped_stats = df.groupby('group').agg({
        'value1': ['sum', 'mean', 'count'],
        'value2': ['min', 'max']
    }).round(2)

    # Flatten column names
    grouped_stats.columns = [f"{col[0]}_{col[1]}" for col in grouped_stats.columns]
    grouped_stats = grouped_stats.reset_index()

    grouped_stats
    return df, grouped_stats, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
