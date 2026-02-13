# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Plotly: Financial Chart with Volume

        Create an interactive financial chart combining candlesticks and volume bars.
        Common usage: `go.Figure(data=[go.Candlestick(x=df.index, open=df.Open)])`.
        """
    )
    return


@app.cell
def __():
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import pandas as pd
    import numpy as np
    
    # Generate sample OHLCV data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    price = 100 + np.random.randn(len(dates)).cumsum()
    
    df = pd.DataFrame({
        'Open': price + np.random.randn(len(dates)),
        'High': price + abs(np.random.randn(len(dates))*2),
        'Low': price - abs(np.random.randn(len(dates))*2),
        'Close': price + np.random.randn(len(dates)),
        'Volume': np.random.randint(1000, 10000, len(dates))
    }, index=dates)
    
    # Create figure with secondary y-axis
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
        shared_xaxes=True
    )
    
    # Add candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df.Open,
            high=df.High,
            low=df.Low,
            close=df.Close,
            name="OHLC"
        ),
        row=1, col=1
    )
    
    # Add volume bars
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df.Volume,
            name="Volume"
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        title="Stock Price and Volume Analysis",
        xaxis_rangeslider_visible=False,
        height=800
    )
    
    fig
    return fig, go, make_subplots, pd, np


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
