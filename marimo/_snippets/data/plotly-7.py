# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: 3D Scatter Plot with Clusters

        Create an interactive 3D scatter plot for dimensional analysis.
        Common usage: `fig = px.scatter_3d(df, x='x', y='y', z='z', color='cluster')`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import numpy as np
    import pandas as pd
    from sklearn.datasets import make_blobs

    # Generate clustered 3D data
    n_samples = 300
    n_clusters = 4

    X, labels = make_blobs(
        n_samples=n_samples,
        n_features=3,
        centers=n_clusters,
        random_state=42
    )

    df = pd.DataFrame(
        X,
        columns=['x', 'y', 'z']
    )
    df['cluster'] = labels

    # Create 3D scatter plot
    fig = px.scatter_3d(
        df,
        x='x',
        y='y',
        z='z',
        color='cluster',
        title='3D Cluster Visualization',
        labels={'cluster': 'Cluster'},
        opacity=0.7
    )

    # Update layout for better interactivity
    fig.update_layout(
        scene=dict(
            camera=dict(
                up=dict(x=0, y=0, z=1),
                center=dict(x=0, y=0, z=0),
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        )
    )

    fig
    return X, df, fig, labels, make_blobs, n_clusters, n_samples, np, pd, px


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
