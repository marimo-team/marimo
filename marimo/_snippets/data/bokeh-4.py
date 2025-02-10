# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Interactive Dashboard Layout

        Create a multi-panel dashboard with different visualization types.
        Common usage: `column(row(p1, p2), p3)` for complex layouts.
        Commonly used in: business analytics, KPI monitoring, data reporting.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource
    from bokeh.layouts import column, row
    import numpy as np
    import pandas as pd
    
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    
    data = pd.DataFrame({
        'date': dates,
        'metric1': np.random.normal(100, 15, len(dates)).cumsum(),
        'metric2': np.random.normal(50, 10, len(dates)).cumsum(),
        'category': np.random.choice(['A', 'B', 'C'], len(dates)),
        'value': np.random.uniform(20, 80, len(dates))
    })
    
    # Create data sources
    ts_source = ColumnDataSource(data)
    cat_source = data.groupby('category')['value'].mean().reset_index()
    cat_source = ColumnDataSource(cat_source)
    
    # Time series plot
    p1 = figure(
        height=300,
        width=800,
        title='Metrics Over Time',
        x_axis_type='datetime',
        tools='pan,box_zoom,wheel_zoom,reset'
    )
    
    p1.line('date', 'metric1', line_color='navy', legend_label='Metric 1',
            source=ts_source)
    p1.line('date', 'metric2', line_color='crimson', legend_label='Metric 2',
            source=ts_source)
    p1.legend.click_policy = 'hide'
    
    # Bar chart
    p2 = figure(
        height=300,
        width=400,
        title='Average by Category',
        x_range=list(data.category.unique()),
        tools='pan,box_zoom,wheel_zoom,reset'
    )
    
    p2.vbar(x='category', top='value', width=0.8, source=cat_source,
            fill_color='navy', line_color=None)
    
    # Distribution plot
    hist, edges = np.histogram(data.value, bins=20)
    hist_data = pd.DataFrame({
        'count': hist,
        'left': edges[:-1],
        'right': edges[1:]
    })
    hist_source = ColumnDataSource(hist_data)
    
    p3 = figure(
        height=300,
        width=400,
        title='Value Distribution',
        tools='pan,box_zoom,wheel_zoom,reset'
    )
    
    p3.quad(top='count', bottom=0, left='left', right='right',
            source=hist_source, fill_color='navy', line_color='white')
    
    # Style all plots
    for p in [p1, p2, p3]:
        p.grid.grid_line_alpha = 0.3
        p.axis.axis_label_text_font_size = '12pt'
    
    # Create layout
    layout = column(
        p1,
        row(p2, p3)
    )
    
    layout
    return (ColumnDataSource, cat_source, column, data, dates, edges, figure,
            hist, hist_data, hist_source, layout, np, p1, p2, p3, pd, row,
            ts_source)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
