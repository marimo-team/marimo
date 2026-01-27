# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Geographic Data Visualization

        Create interactive maps with dynamic overlays.
        Common usage: Geospatial analysis, location-based analytics.
        Commonly used in: GIS analysis, location intelligence.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    
    hv.extension('bokeh')
    
    # Generate sample location data
    np.random.seed(42)
    n_points = 100
    
    # Sample data for US locations
    data = pd.DataFrame({
        'latitude': np.random.uniform(25, 48, n_points),
        'longitude': np.random.uniform(-125, -70, n_points),
        'value': np.random.normal(100, 15, n_points),
        'category': np.random.choice(['A', 'B', 'C'], n_points)
    })
    
    # Create tile source and points
    tiles = hv.element.tiles.OSM()
    points = hv.Points(
        data, 
        ['longitude', 'latitude'], 
        ['value', 'category']
    )
    
    # Create map view with options
    map_view = (tiles * points).options(
        width=700,
        height=500,
        title='Geographic Distribution'
    )
    
    # Style the points with tooltips
    points.options(
        color='value',
        cmap='viridis',
        size=8,
        tools=['hover', 'box_select'],
        colorbar=True,
        alpha=0.6,
        hover_tooltips=[
            ('Category', '@category'),
            ('Value', '@value{0.00}'),
            ('Location', '(@longitude, @latitude)')
        ]
    )
    
    map_view
    return data, hv, map_view, n_points, np, pd, points, tiles


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
