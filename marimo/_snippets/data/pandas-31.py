# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Advanced DateTime Operations""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample DataFrame with datetime data
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=5),
        'value': [100, 200, 150, 300, 250]
    })

    # DateTime operations
    date_features = pd.DataFrame({
        'original_date': df['date'],
        'year': df['date'].dt.year,
        'month': df['date'].dt.month,
        'day': df['date'].dt.day,
        'day_name': df['date'].dt.day_name(),
        'is_month_end': df['date'].dt.is_month_end
    })

    date_features
    return date_features, df, pd


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
