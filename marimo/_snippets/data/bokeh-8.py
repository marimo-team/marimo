# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Interactive Heatmap with Clustering

        Create a heatmap with hierarchical clustering for correlation analysis.
        Common usage: Feature correlation analysis, pattern detection.
        Commonly used in: data science, bioinformatics, financial analysis.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, LinearColorMapper, ColorBar
    from bokeh.transform import transform
    import numpy as np
    import pandas as pd
    from scipy.cluster import hierarchy
    from scipy.spatial.distance import pdist
    
    # Generate correlated data
    np.random.seed(42)
    n_features = 10
    n_samples = 1000
    
    # Create feature names
    features = [f'Feature_{i+1}' for i in range(n_features)]
    
    # Generate data with some correlations
    data = np.random.randn(n_samples, n_features)
    data[:, 1] = data[:, 0] + np.random.randn(n_samples) * 0.3
    data[:, 4] = data[:, 3] - np.random.randn(n_samples) * 0.2
    
    df = pd.DataFrame(data, columns=features)
    
    # Compute correlation matrix
    corr = df.corr()
    
    # Perform hierarchical clustering
    linkage = hierarchy.linkage(pdist(corr), method='ward')
    order = hierarchy.leaves_list(linkage)
    
    # Reorder correlation matrix
    corr = corr.iloc[order, order]
    
    # Prepare data for heatmap
    source = ColumnDataSource(data=dict(
        x=[(i+0.5) for i in range(n_features) for _ in range(n_features)],
        y=[(i+0.5) for _ in range(n_features) for i in range(n_features)],
        correlation=corr.values.flatten(),
        xname=[corr.index[i] for i in range(n_features) for _ in range(n_features)],
        yname=[corr.columns[i] for _ in range(n_features) for i in range(n_features)]
    ))
    
    # Create color mapper
    mapper = LinearColorMapper(
        palette='RdBu11',
        low=-1,
        high=1
    )
    
    # Create figure
    p = figure(
        width=600,
        height=600,
        title='Feature Correlation Heatmap',
        x_range=list(corr.index),
        y_range=list(reversed(corr.columns)),
        tools='pan,box_zoom,wheel_zoom,reset,save,hover',
        x_axis_location='above'
    )
    
    # Add heatmap rectangles
    p.rect(
        x='x',
        y='y',
        width=1,
        height=1,
        source=source,
        fill_color=transform('correlation', mapper),
        line_color=None
    )
    
    # Add color bar
    color_bar = ColorBar(
        color_mapper=mapper,
        location=(0, 0),
        title='Correlation',
        orientation='horizontal'
    )
    
    p.add_layout(color_bar, 'below')
    
    # Style the plot
    p.grid.grid_line_color = None
    p.axis.axis_line_color = None
    p.axis.major_tick_line_color = None
    p.xaxis.major_label_orientation = 0.7
    p.yaxis.major_label_orientation = 0
    
    # Add hover tooltips
    p.hover.tooltips = [
        ('Features', '@xname vs @yname'),
        ('Correlation', '@correlation{0.00}')
    ]
    
    p
    return (ColorBar, ColumnDataSource, LinearColorMapper, corr, data, df,
            features, figure, hierarchy, linkage, mapper, n_features, n_samples,
            np, order, p, pd, pdist, source, transform)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
