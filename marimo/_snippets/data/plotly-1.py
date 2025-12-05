# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Interactive Scatter Plot with Categories

        Create a scatter plot with categorical coloring and size mapping.
        Common usage: `fig = px.scatter(df, x="col1", y="col2", color="category", size="values")`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import numpy as np

    # Sample data
    np.random.seed(42)
    n_points = 50

    data = {
        'x': np.random.normal(0, 1, n_points),
        'y': np.random.normal(0, 1, n_points),
        'size': np.random.uniform(5, 25, n_points),
        'group': [f"Group {i}" for i in np.random.randint(1, 4, n_points)]
    }

    # Create interactive scatter plot
    fig = px.scatter(
        data,
        x='x',
        y='y',
        size='size',
        color='group',
        title="Interactive Grouped Scatter",
        labels={'x': 'X Value', 'y': 'Y Value', 'size': 'Size Value'},
        hover_data=['group', 'size']
    )

    # Update layout
    fig.update_layout(
        hovermode='closest'
    )

    fig
    return data, fig, n_points, np, px


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
