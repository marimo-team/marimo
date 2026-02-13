# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Time Series Analysis

        Create interactive time series visualizations with linked views.
        Common usage: Financial analysis, sensor data monitoring.
        Commonly used in: Trading analysis, IoT monitoring, performance tracking.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    
    # Enable Bokeh backend
    hv.extension('bokeh')
    
    # Generate sample time series data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    n_points = len(dates)
    
    # Create multiple metrics (e.g., stock data)
    df = pd.DataFrame({
        'date': dates,
        'price': 100 + np.random.randn(n_points).cumsum(),
        'volume': np.random.randint(1000, 5000, n_points),
        'volatility': np.abs(np.random.randn(n_points))
    })
    
    # Calculate moving averages
    df['MA20'] = df['price'].rolling(window=20).mean()
    df['MA50'] = df['price'].rolling(window=50).mean()
    
    # Create main price plot
    price_plot = hv.Curve(df, 'date', 'price', label='Price')
    ma20_plot = hv.Curve(df, 'date', 'MA20', label='20-day MA')
    ma50_plot = hv.Curve(df, 'date', 'MA50', label='50-day MA')
    
    # Combine price plots
    price_overlay = (price_plot * ma20_plot * ma50_plot).opts(
        width=800,
        height=300,
        tools=['hover', 'box_zoom', 'wheel_zoom', 'pan', 'reset'],
        title='Price and Moving Averages',
        legend_position='top_left',
        show_grid=True
    )
    
    # Create volume bars
    volume_plot = hv.Bars(df, 'date', 'volume').opts(
        width=800,
        height=150,
        tools=['hover'],
        title='Trading Volume',
        color='navy',
        alpha=0.5
    )
    
    # Create volatility heatmap
    volatility_plot = hv.HeatMap(
        df.assign(month=df.date.dt.month, 
                 day=df.date.dt.day)[['month', 'day', 'volatility']]
    ).opts(
        width=400,
        height=300,
        tools=['hover'],
        title='Volatility Heatmap',
        colorbar=True,
        cmap='RdYlBu_r'
    )
    
    # Layout all plots
    layout = (price_overlay + volume_plot + volatility_plot).cols(1)
    layout.opts(
        title='Interactive Time Series Analysis'
    )
    
    layout
    return (df, dates, hv, layout, ma20_plot, ma50_plot, n_points, np, pd,
            price_overlay, price_plot, volume_plot, volatility_plot)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
