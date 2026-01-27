# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Linked Selection Analysis

        Create linked views with dynamic statistics.
        Common usage: Multi-dimensional data exploration.
        Commonly used in: Feature analysis, correlation studies.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    from holoviews import streams
    
    hv.extension('bokeh')
    
    # Generate sample data
    np.random.seed(42)
    n_points = 1000
    
    # Create correlated features
    x = np.random.normal(0, 1, n_points)
    y = x * 0.5 + np.random.normal(0, 0.5, n_points)
    z = x * -0.2 + y * 0.3 + np.random.normal(0, 0.3, n_points)
    
    data = pd.DataFrame({
        'x': x, 
        'y': y, 
        'z': z
    })
    
    # Create scatter plot with selection stream
    scatter = hv.Points(data, ['x', 'y'])
    selection = streams.Selection1D(source=scatter)
    
    # Create initial histogram
    hist = hv.Histogram(np.histogram(data['z'], bins=20))
    
    # Dynamic histogram of selected points
    def selected_hist(index):
        if len(index):
            selected = data.iloc[index]['z']
            return hv.Histogram(np.histogram(selected, bins=20)).options(
                fill_color='navy'
            )
        return hist.options(fill_color='gray')
    
    dmap = hv.DynamicMap(selected_hist, streams=[selection])
    
    # Layout with styling
    layout = (scatter + dmap).cols(2)
    
    # Style scatter plot
    scatter.options(
        tools=['box_select', 'lasso_select', 'hover'],
        width=400,
        height=400,
        color='navy',
        alpha=0.6,
        title='Select Points',
        hover_tooltips=[
            ('x', '@x{0.2f}'),
            ('y', '@y{0.2f}')
        ]
    )
    
    # Style histogram
    dmap.options(
        width=400,
        height=400,
        title='Distribution (Selected vs All)',
        xlabel='z value',
        ylabel='Count'
    )
    
    layout
    return data, dmap, hist, hv, layout, n_points, np, pd, scatter, selection, streams


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
