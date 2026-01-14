# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Bokeh: Interactive Line Plot

        Create an interactive line plot with pan, zoom, and hover tools.
        Common usage: `figure(tools='pan,box_zoom,reset,save')`.
        Commonly used in: time series analysis, trend visualization.
        """
    )
    return


@app.cell
def _():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource
    import numpy as np

    # Generate sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x) + np.random.normal(0, 0.1, 100)

    # Create data source
    source = ColumnDataSource(data=dict(x=x, y=y))

    # Create figure with tools
    p = figure(
        height=400,
        width=700,
        tools='pan,box_zoom,wheel_zoom,reset,save,hover',
        title='Interactive Line Plot'
    )

    # Add line with hover tooltips
    p.line('x', 'y', line_width=2, source=source)
    p.hover.tooltips = [
        ('x', '@x{0.00}'),
        ('y', '@y{0.00}')
    ]

    p
    return ColumnDataSource, figure, np, p, source, x, y


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
