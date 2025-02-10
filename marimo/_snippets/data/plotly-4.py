# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Multiple Metrics Dashboard

        Create a dashboard-style layout with multiple plots using subplots.
        Common usage: `make_subplots(rows=2, cols=2)` followed by `add_trace()` for each plot.
        """
    )
    return


@app.cell
def _():
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np
    import pandas as pd

    # Generate sample data
    np.random.seed(42)
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x) + np.random.normal(0, 0.1, 100)
    y2 = np.cumsum(np.random.randn(100))
    y3 = np.random.normal(0, 1, 100)

    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Time Series', 'Cumulative Sum', 
                       'Distribution', 'Moving Average')
    )

    # Add traces
    fig.add_trace(
        go.Scatter(x=x, y=y1, name="Time Series"),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(x=x, y=y2, name="Cumulative"),
        row=1, col=2
    )

    fig.add_trace(
        go.Histogram(x=y3, name="Distribution"),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(x=x, y=pd.Series(y1).rolling(10).mean(), 
                  name="Moving Avg"),
        row=2, col=2
    )

    # Update layout
    fig.update_layout(
        height=800,
        showlegend=False,
        title_text="Multiple Metrics Dashboard"
    )

    fig
    return fig, go, make_subplots, np, pd, x, y1, y2, y3


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
