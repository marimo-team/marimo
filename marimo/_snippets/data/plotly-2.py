# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Time Series with Range Selector

        Create an interactive time series plot with built-in range selector and slider.
        Common usage: `fig = px.line(df, x="date_column", y="value_column")`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import pandas as pd
    import numpy as np

    # Generate sample time series data
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    values = np.cumsum(np.random.randn(len(dates))) + 100

    df = pd.DataFrame({
        'date': dates,
        'value': values
    })

    # Create interactive time series
    fig = px.line(
        df,
        x='date',
        y='value',
        title='Interactive Time Series'
    )

    # Add range selector and slider
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(step="all", label="All")
                ]
            ),
            rangeslider=dict(visible=True)
        )
    )

    fig
    return dates, df, fig, np, pd, px, values


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
