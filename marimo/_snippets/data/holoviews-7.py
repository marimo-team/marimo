# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Advanced Data Analysis Suite

        Create interactive visualizations for comprehensive data analysis.
        Common usage: Multi-dimensional analysis, pattern discovery.
        Domains: Data Science, Research, Business Intelligence.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    from holoviews import opts
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    
    hv.extension('bokeh')
    
    # Generate sample dataset
    np.random.seed(42)
    n_samples = 1000
    
    # Create multi-dimensional dataset
    data = pd.DataFrame({
        'feature1': np.random.normal(0, 1, n_samples),
        'feature2': np.random.normal(0, 1, n_samples),
        'feature3': np.random.normal(0, 1, n_samples),
        'target': np.random.normal(0, 1, n_samples)
    })
    
    # Add correlations
    data['feature2'] += data['feature1'] * 0.5
    data['feature3'] += data['feature2'] * 0.3
    data['target'] += data['feature1'] * 0.6 + data['feature2'] * 0.3
    
    # Create bivariate distribution plot
    bivariate = hv.Bivariate(
        (data['feature1'], data['feature2'])
    ).options(
        width=300,
        height=300,
        cmap='viridis',
        title='Feature Distribution'
    )
    
    # Create scatter with marginal distributions
    scatter = hv.Points((data['feature1'], data['target'])).options(
        color='navy',
        alpha=0.6,
        width=300,
        height=300,
        tools=['box_select', 'lasso_select']
    )
    
    marginal_x = hv.Histogram(np.histogram(data['feature1'], bins=30))
    marginal_y = hv.Histogram(np.histogram(data['target'], bins=30))
    
    # Cluster the data
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data)
    kmeans = KMeans(n_clusters=3, random_state=42)
    clusters = kmeans.fit_predict(scaled_data)
    
    # Create cluster visualization
    cluster_viz = hv.Points(
        pd.DataFrame({
            'x': data['feature1'],
            'y': data['feature2'],
            'Cluster': clusters.astype(str)
        }),
        kdims=['x', 'y'],
        vdims=['Cluster']
    ).options(
        color='Cluster',
        cmap='Category10',
        width=300,
        height=300,
        title='Cluster Analysis',
        tools=['hover']
    )
    
    # Combine visualizations
    layout = (
        bivariate + 
        (scatter << marginal_x << marginal_y) + 
        cluster_viz
    ).cols(3)
    
    layout
    return (bivariate, cluster_viz, clusters, data, hv, kmeans, layout, marginal_x,
            marginal_y, n_samples, np, opts, pd, scaler, scaled_data, scatter)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run() 