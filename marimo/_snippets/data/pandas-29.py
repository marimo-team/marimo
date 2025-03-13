# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""# Pandas: Rolling and Expanding Window Statistics""")
    return


@app.cell
def _():
    import pandas as pd

    # Create sample time series DataFrame
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=5),
        'value': [10, 20, 15, 30, 25]
    }).set_index('date')

    # Calculate multiple window statistics
    window_stats = pd.DataFrame({
        'original': df['value'],
        'rolling_mean': df['value'].rolling(window=3).mean(),
        'rolling_std': df['value'].rolling(window=3).std(),
        'expanding_max': df['value'].expanding().max()
    })

    window_stats
    return df, pd, window_stats


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
