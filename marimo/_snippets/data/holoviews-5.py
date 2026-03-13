# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Time Series Analysis

        Create interactive time series with dynamic updates.
        Common usage: Real-time monitoring, financial analysis.
        Commonly used in: Trading systems, IoT monitoring, performance tracking.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    from datetime import datetime, timedelta
    
    hv.extension('bokeh')
    
    # Generate time series data
    np.random.seed(42)
    now = datetime.now()
    dates = [now - timedelta(minutes=i) for i in range(100, 0, -1)]
    
    # Simulate multiple metrics (e.g., system metrics)
    data = pd.DataFrame({
        'time': dates,
        'value1': np.random.normal(100, 10, 100).cumsum(),
        'value2': np.random.normal(50, 5, 100).cumsum(),
        'anomaly': np.random.choice([0, 1], 100, p=[0.95, 0.05])
    })
    
    # Create main time series plot
    curve1 = hv.Curve(
        data, kdims=['time'], vdims=['value1'], 
        label='Metric 1'
    )
    curve2 = hv.Curve(
        data, kdims=['time'], vdims=['value2'], 
        label='Metric 2'
    )
    
    # Add anomaly points
    anomalies = data[data['anomaly'] == 1]
    points = hv.Points(
        anomalies, kdims=['time', 'value1'],
        label='Anomalies'
    )
    
    # Style the plots
    curve1 = curve1.options(color='navy', line_width=2)
    curve2 = curve2.options(color='green', line_width=2)
    points = points.options(color='red', size=10)
    
    # Combine plots with styling
    plot = (curve1 * curve2 * points).options(
        width=800,
        height=400,
        title='Real-time Metrics with Anomaly Detection',
        tools=['hover', 'box_zoom', 'wheel_zoom', 'reset'],
        legend_position='top_right',
        xlabel='Time',
        ylabel='Value'
    )
    
    plot
    return (anomalies, curve1, curve2, data, dates, datetime, hv, now, np, pd,
            plot, points, timedelta)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run() 