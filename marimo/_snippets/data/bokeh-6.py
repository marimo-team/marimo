# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Time Series with Range Tool

        Create a time series plot with range selection tool.
        Common usage: Financial analysis, trend analysis with zoom capability.
        Commonly used in: stock analysis, sensor data analysis, trend investigation.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, RangeTool
    import numpy as np
    import pandas as pd
    
    # Generate sample time series data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    
    # Simulate stock price with trend and volatility
    base = 100
    trend = np.linspace(0, 20, len(dates))
    volatility = np.random.normal(0, 1, len(dates)).cumsum()
    price = base + trend + volatility
    volume = np.random.uniform(50000, 200000, len(dates))
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'price': price,
        'volume': volume,
        'ma20': pd.Series(price).rolling(window=20).mean(),
        'ma50': pd.Series(price).rolling(window=50).mean()
    })
    
    source = ColumnDataSource(df)
    
    # Create main figure
    p = figure(
        height=400,
        width=800,
        title='Interactive Time Series Analysis',
        x_axis_type='datetime',
        tools='pan,wheel_zoom,box_zoom,reset,save'
    )
    
    # Add price and moving averages
    p.line('date', 'price', line_color='gray', line_alpha=0.6,
           legend_label='Price', source=source)
    p.line('date', 'ma20', line_color='blue', line_width=2,
           legend_label='20-day MA', source=source)
    p.line('date', 'ma50', line_color='red', line_width=2,
           legend_label='50-day MA', source=source)
    
    # Create range tool figure
    select = figure(
        height=150,
        width=800,
        y_axis_type=None,
        x_axis_type='datetime',
        tools='',
        toolbar_location=None
    )
    
    range_tool = RangeTool(x_range=p.x_range)
    range_tool.overlay.fill_color = 'navy'
    range_tool.overlay.fill_alpha = 0.2
    
    select.line('date', 'price', source=source)
    select.ygrid.grid_line_color = None
    select.add_tools(range_tool)
    
    # Style the plots
    p.grid.grid_line_alpha = 0.3
    p.xaxis.axis_label = 'Date'
    p.yaxis.axis_label = 'Price'
    
    # Add hover tooltips
    p.hover.tooltips = [
        ('Date', '@date{%F}'),
        ('Price', '@price{0.00}'),
        ('MA20', '@ma20{0.00}'),
        ('MA50', '@ma50{0.00}'),
        ('Volume', '@volume{0,0}')
    ]
    p.hover.formatters = {'@date': 'datetime'}
    
    # Configure legend
    p.legend.location = 'top_left'
    p.legend.click_policy = 'hide'
    
    from bokeh.layouts import column
    layout = column(p, select)
    
    layout
    return (ColumnDataSource, RangeTool, base, column, dates, df, figure, layout,
            np, p, pd, price, range_tool, select, source, trend, volatility,
            volume)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
