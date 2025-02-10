# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Essential Plot Types with `holoviews`

        Create fundamental visualizations using the `holoviews` library.
        Common usage: Basic data visualization, statistical plotting.
        Commonly used in: Data analysis, research, reporting.
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
    x = np.linspace(0, 10, 50)
    y = np.sin(x) + np.random.normal(0, 0.1, 50)
    categories = ['A', 'B', 'C', 'D']
    values = np.random.normal(10, 2, len(categories))
    
    # Create basic plots
    curve = hv.Curve((x, y), 'x', 'y').options(
        width=300, height=200, color='navy',
        title='Curve Plot'
    )
    
    bars = hv.Bars(({'category': categories, 'value': values}), 
                   'category', 'value').options(
        width=300, height=200, color='green',
        title='Bar Plot'
    )
    
    area = hv.Area((x, y)).options(
        width=300, height=200, color='purple', alpha=0.5,
        title='Area Plot'
    )
    
    spikes = hv.Spikes((x, np.abs(y))).options(
        width=300, height=200, color='red',
        title='Spike Plot'
    )
    
    # Combine in layout
    layout = (curve + bars + area + spikes).cols(2).options(
        title='Basic Plot Types'
    )
    
    layout
    return area, bars, categories, curve, hv, layout, np, pd, spikes, values, x, y


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
