# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Correlation Heatmap

        Create an interactive correlation heatmap with customizable color scale.
        Common usage: `fig = px.imshow(df.corr(), color_continuous_scale='RdBu_r')`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import pandas as pd
    import numpy as np

    # Generate sample correlated data
    np.random.seed(42)
    n_samples = 100
    df = pd.DataFrame({
        'A': np.random.normal(0, 1, n_samples),
        'B': np.random.normal(0, 1, n_samples),
        'C': np.random.normal(0, 1, n_samples),
        'D': np.random.normal(0, 1, n_samples)
    })
    df['B'] = df['A'] * 0.8 + np.random.normal(0, 0.2, n_samples)
    df['D'] = -df['C'] * 0.6 + np.random.normal(0, 0.3, n_samples)

    # Create correlation matrix
    corr_matrix = df.corr()

    # Create heatmap
    fig = px.imshow(
        corr_matrix,
        color_continuous_scale='RdBu_r',
        aspect='auto',
        title='Correlation Matrix Heatmap'
    )

    # Update layout
    fig.update_layout(
        xaxis_title="Features",
        yaxis_title="Features",
        coloraxis_colorbar_title="Correlation"
    )

    fig
    return corr_matrix, df, fig, n_samples, np, pd, px


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
