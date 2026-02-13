# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Interactive Data Exploration

        Create interactive visualizations with linked views.
        Common usage: Exploratory data analysis with linked selections.
        Commonly used in: Data science workflows, interactive dashboards.
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
    
    # Generate sample data
    np.random.seed(42)
    n_points = 1000
    
    df = pd.DataFrame({
        'x': np.random.normal(0, 1, n_points),
        'y': np.random.normal(0, 1, n_points),
        'category': np.random.choice(['A', 'B', 'C'], n_points),
        'value': np.random.uniform(0, 100, n_points)
    })
    
    # Create scatter plot with hover
    scatter = hv.Points(df, kdims=['x', 'y'], vdims=['category', 'value'])
    scatter.opts(
        tools=['hover', 'box_select'],
        size=8,
        color='category',
        cmap='Category10',
        width=400,
        height=400,
        title='Interactive Scatter Plot'
    )
    
    # Create linked histogram
    hist = hv.operation.histogram(scatter, dimension='value', normed=False)
    hist.opts(
        tools=['hover'],
        width=400,
        height=200,
        title='Value Distribution'
    )
    
    # Layout plots
    layout = (scatter + hist).cols(1)
    layout.opts(
        title='Data Exploration Dashboard'
    )
    
    layout
    return df, hist, hv, layout, n_points, np, pd, scatter


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
