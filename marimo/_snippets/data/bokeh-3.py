# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Real-time Data Streaming

        Create a real-time streaming visualization with rolling window.
        Common usage: `ColumnDataSource` with periodic updates.
        Commonly used in: system monitoring, IoT dashboards, live analytics.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, DatetimeTickFormatter
    import numpy as np
    from datetime import datetime, timedelta
    import pandas as pd
    
    # Initialize data with rolling window
    window_size = 100
    now = datetime.now()
    times = [(now + timedelta(seconds=i)) for i in range(-window_size, 0)]
    
    # Simulate metric data (e.g., system metrics)
    values = np.random.normal(100, 10, window_size)
    values_smooth = pd.Series(values).rolling(window=5).mean()
    
    # Create data source
    source = ColumnDataSource(data=dict(
        time=times,
        value=values,
        value_smooth=values_smooth
    ))
    
    # Create figure
    p = figure(
        height=400,
        width=800,
        title='Real-time Metric Monitoring',
        x_axis_type='datetime',
        tools='pan,box_zoom,wheel_zoom,reset,save'
    )
    
    # Add raw data line
    p.line('time', 'value', 
           line_color='lightgray',
           line_alpha=0.5,
           line_width=1,
           legend_label='Raw Data',
           source=source)
    
    # Add smoothed line
    p.line('time', 'value_smooth',
           line_color='navy',
           line_width=2,
           legend_label='Smoothed (5-point MA)',
           source=source)
    
    # Style the plot
    p.grid.grid_line_alpha = 0.3
    p.xaxis.formatter = DatetimeTickFormatter(
        seconds="%Y-%m-%d %H:%M:%S",
        minsec="%Y-%m-%d %H:%M:%S",
        minutes="%Y-%m-%d %H:%M:%S",
        hourmin="%Y-%m-%d %H:%M"
    )
    p.xaxis.axis_label = 'Time'
    p.yaxis.axis_label = 'Value'
    
    # Add hover tool
    p.hover.tooltips = [
        ('Time', '@time{%Y-%m-%d %H:%M:%S}'),
        ('Value', '@value{0.00}'),
        ('Smoothed', '@value_smooth{0.00}')
    ]
    p.hover.formatters = {'@time': 'datetime'}
    
    # Configure legend
    p.legend.location = 'top_left'
    p.legend.click_policy = 'hide'
    
    p
    return (ColumnDataSource, DatetimeTickFormatter, datetime, figure, now, np, p,
            pd, source, timedelta, times, values, values_smooth, window_size)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
