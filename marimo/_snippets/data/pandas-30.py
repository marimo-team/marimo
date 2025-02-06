# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Missing Data Handling""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame with missing values
    df = pd.DataFrame({
        'A': [1, None, 3, None, 5],
        'B': [None, 2, 3, 4, 5],
        'C': ['a', 'b', None, 'd', 'e']
    })

    # Common missing data operations
    cleaned_df = df.copy()
    cleaned_df['A'] = df['A'].fillna(df['A'].mean())  # Fill numeric with mean
    cleaned_df['B'] = df['B'].fillna(0)  # Fill numeric with zero
    cleaned_df['C'] = df['C'].fillna('missing')  # Fill strings with value

    cleaned_df
    return cleaned_df, df, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
