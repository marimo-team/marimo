# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Clustering Analysis Visualization

        Create an interactive heatmap with dendrograms for hierarchical clustering analysis.
        Common usage: `fig = ff.create_dendrogram(X)` and `px.imshow(correlation_matrix)`.
        Commonly used in: feature correlation analysis, gene expression analysis, customer segmentation.
        """
    )
    return


@app.cell
def _():
    import plotly.figure_factory as ff
    import plotly.express as px
    from scipy.cluster.hierarchy import linkage
    import numpy as np
    import pandas as pd

    # Generate sample data
    np.random.seed(42)
    n_features = 10
    n_samples = 100

    # Create feature names
    feature_names = [f'Feature_{i}' for i in range(n_features)]

    # Generate correlated data
    data = np.random.randn(n_samples, n_features)
    data[:, 1] = data[:, 0] + np.random.randn(n_samples) * 0.3  # Correlate features 0 and 1
    data[:, 4] = data[:, 3] - np.random.randn(n_samples) * 0.2  # Correlate features 3 and 4

    df = pd.DataFrame(data, columns=feature_names)

    # Compute correlation matrix
    corr_matrix = df.corr()

    # Compute linkage for dendrogram
    linkage_matrix = linkage(corr_matrix, 'ward')

    # Create dendrogram
    fig_dendrogram = ff.create_dendrogram(
        corr_matrix,
        labels=feature_names,
        color_threshold=1.5
    )
    fig_dendrogram.update_layout(
        title='Feature Clustering Dendrogram',
        width=800,
        height=400
    )

    # Create heatmap
    fig_heatmap = px.imshow(
        corr_matrix,
        labels=dict(x="Features", y="Features", color="Correlation"),
        x=feature_names,
        y=feature_names,
        color_continuous_scale="RdBu_r",
        aspect="auto"
    )
    fig_heatmap.update_layout(
        title='Feature Correlation Heatmap',
        width=800,
        height=800
    )

    # Display both visualizations
    fig_dendrogram
    fig_heatmap
    return (
        corr_matrix,
        data,
        df,
        feature_names,
        ff,
        fig_dendrogram,
        fig_heatmap,
        linkage,
        linkage_matrix,
        n_features,
        n_samples,
        np,
        pd,
        px,
    )


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
