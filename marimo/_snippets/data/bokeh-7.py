# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Categorical Data Analysis

        Create interactive bar charts and heatmaps for categorical data.
        Common usage: Comparing metrics across categories and subcategories.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, FactorRange
    from bokeh.transform import factor_cmap
    import numpy as np
    import pandas as pd
    
    # Sample data
    categories = ['A', 'B', 'C']
    regions = ['North', 'South', 'East']
    
    data = []
    np.random.seed(42)
    
    for cat in categories:
        for region in regions:
            data.append({
                'category': cat,
                'region': region,
                'sales': np.random.randint(50, 150)
            })
    
    df = pd.DataFrame(data)
    factors = [(cat, region) for cat in categories for region in regions]
    
    # Create bar chart
    p = figure(
        height=400,
        width=600,
        title='Sales by Category and Region',
        x_range=FactorRange(*factors),
        tools='pan,box_zoom,reset,hover'
    )
    
    # Add bars
    p.vbar(
        x='category_region',
        top='sales',
        width=0.9,
        source=ColumnDataSource(df.assign(
            category_region=list(zip(df.category, df.region))
        )),
        fill_color=factor_cmap(
            'category_region',
            ['#1f77b4', '#ff7f0e', '#2ca02c']*3,
            factors
        )
    )
    
    # Style
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = 0.7
    
    # Tooltips
    p.hover.tooltips = [
        ('Category', '@category'),
        ('Region', '@region'),
        ('Sales', '@sales')
    ]
    
    p
    return ColumnDataSource, FactorRange, df, factor_cmap, factors, figure, p


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
