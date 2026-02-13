# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Linked Brushing and Selection

        Create linked plots with synchronized selection.
        Common usage: `layout([p1, p2])` with shared `ColumnDataSource`.
        Commonly used in: exploratory data analysis, correlation analysis, outlier detection.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource
    from bokeh.layouts import row
    import numpy as np
    
    # Generate sample data
    np.random.seed(42)
    N = 1000
    x = np.random.normal(0, 1, N)
    y = x * 0.5 + np.random.normal(0, 0.5, N)  # Positive correlation with x
    z = x * -0.2 + np.random.normal(0, 0.2, N)  # Negative correlation with x
    
    # Create data source
    source = ColumnDataSource(data=dict(x=x, y=y, z=z))
    
    # Common figure properties
    plot_config = dict(
        height=400,
        width=400,
        tools='box_select,lasso_select,wheel_zoom,pan,reset,hover',
        background_fill_color='#f5f5f5'
    )
    
    # Create first plot
    p1 = figure(
        title='Y vs X (Positive Correlation)',
        **plot_config
    )
    p1.circle('x', 'y', 
              source=source,
              size=8,
              fill_color='navy',
              fill_alpha=0.5,
              line_color='white',
              selection_color='red',
              nonselection_alpha=0.1)
    
    # Create second plot
    p2 = figure(
        title='Z vs X (Negative Correlation)',
        **plot_config
    )
    p2.circle('x', 'z', 
              source=source,
              size=8,
              fill_color='navy',
              fill_alpha=0.5,
              line_color='white',
              selection_color='red',
              nonselection_alpha=0.1)
    
    # Add hover tooltips
    tooltip_config = [
        ('x', '@x{0.00}'),
        ('y', '@y{0.00}'),
        ('z', '@z{0.00}')
    ]
    p1.hover.tooltips = tooltip_config
    p2.hover.tooltips = tooltip_config
    
    # Add grid styling
    for p in [p1, p2]:
        p.grid.grid_line_color = 'white'
        p.grid.grid_line_width = 2
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'bold'
    
    # Add axis labels
    p1.xaxis.axis_label = 'X Value'
    p1.yaxis.axis_label = 'Y Value'
    p2.xaxis.axis_label = 'X Value'
    p2.yaxis.axis_label = 'Z Value'
    
    # Layout plots side by side
    layout = row(p1, p2)
    
    layout
    return (ColumnDataSource, figure, layout, np, p1, p2, row, source, x, y, z)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
