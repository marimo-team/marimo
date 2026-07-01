# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Core Plotting with `holoviews`

        Create essential visualizations using the `holoviews` library (imported as `hv`).
        Common usage: Data visualization, exploratory analysis, statistical plotting.
        Commonly used in: Data science, research, interactive dashboards.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    
    hv.extension('bokeh')
    
    # Generate sample data
    np.random.seed(42)
    
    # 1. Basic Scatter with Path overlay
    x = np.linspace(0, 10, 100)
    y = np.sin(x) + np.random.normal(0, 0.1, 100)
    scatter = hv.Scatter((x, y)).options(
        color='navy', size=8, tools=['hover']
    )
    path = hv.Path((x, y)).options(
        line_color='red', line_width=2
    )
    
    # 2. QuadMesh plot (instead of Surface)
    x_range = np.linspace(-2, 2, 20)
    y_range = np.linspace(-2, 2, 20)
    xx, yy = np.meshgrid(x_range, y_range)
    zz = np.sin(xx) * np.cos(yy)
    quadmesh = hv.QuadMesh((x_range, y_range, zz)).options(
        cmap='viridis',
        width=300,
        height=300,
        tools=['hover'],
        title='QuadMesh Plot'
    )
    
    # 3. Contour plot
    contours = hv.Contours((x_range, y_range, zz)).options(
        width=300,
        height=300,
        tools=['hover'],
        title='Contour Plot',
        cmap='viridis'
    )
    
    # 4. Points with color mapping
    points_data = pd.DataFrame({
        'x': np.random.normal(0, 1, 100),
        'y': np.random.normal(0, 1, 100),
        'color': np.random.uniform(0, 1, 100)
    })
    points = hv.Points(points_data, ['x', 'y'], 'color').options(
        color='color',
        cmap='RdYlBu',
        size=8,
        tools=['hover'],
        width=300,
        height=300,
        title='Colored Points'
    )
    
    # Combine plots in layout
    layout = (
        (scatter * path) + 
        quadmesh +
        contours + 
        points
    ).cols(4).options(
        title='HoloViews Plot Gallery'
    )
    
    layout
    return (contours, hv, layout, np, path, pd, points, points_data, quadmesh,
            scatter, x, x_range, xx, y, y_range, yy, zz)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
