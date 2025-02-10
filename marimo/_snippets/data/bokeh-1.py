# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Interactive Scatter Plot

        Create a scatter plot with interactive tools and color mapping.
        Common usage: `figure(tools='box_select,lasso_select,reset')`.
        Commonly used in: data exploration, cluster analysis, outlier detection.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, ColorBar
    from bokeh.transform import linear_cmap
    import numpy as np
    
    # Generate sample clustered data
    np.random.seed(42)
    N = 500
    x = np.random.normal(size=N)
    y = np.random.normal(size=N)
    color_value = np.random.uniform(size=N)  # Value for color mapping
    
    # Create data source
    source = ColumnDataSource(data=dict(
        x=x,
        y=y,
        color=color_value,
    ))
    
    # Create figure with selection tools
    p = figure(
        height=400,
        width=700,
        tools='box_select,lasso_select,wheel_zoom,pan,reset,save',
        title='Interactive Scatter Plot'
    )
    
    # Add points with color mapping
    mapper = linear_cmap('color', 'Viridis256', 0, 1)
    scatter = p.scatter('x', 'y', 
                       size=8,
                       source=source,
                       fill_color=mapper,
                       line_color='white',
                       alpha=0.6,
                       selection_color='red',
                       nonselection_alpha=0.1)
    
    # Add colorbar
    color_bar = ColorBar(color_mapper=mapper['transform'], 
                        width=8,
                        location=(0,0))
    p.add_layout(color_bar, 'right')
    
    # Add hover tooltips
    p.hover.tooltips = [
        ('x', '@x{0.00}'),
        ('y', '@y{0.00}'),
        ('value', '@color{0.00}')
    ]
    
    p
    return (ColorBar, ColumnDataSource, color_bar, color_value, figure, linear_cmap,
            mapper, np, p, scatter, source, x, y)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
