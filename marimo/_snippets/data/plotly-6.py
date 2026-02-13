# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Statistical Distribution Comparison

        Create violin plots with box plots overlay for distribution comparison.
        Common usage: `fig = go.Figure(data=[go.Violin(x=groups, y=values)])`.
        """
    )
    return


@app.cell
def _():
    import plotly.graph_objects as go
    import numpy as np

    # Generate sample data from different distributions
    np.random.seed(42)

    groups = ['A', 'B', 'C']
    data = {
        'A': np.random.normal(0, 1, 200),
        'B': np.random.normal(2, 1.5, 200),
        'C': np.random.exponential(2, 200)
    }

    # Create figure
    fig = go.Figure()

    # Add violin plots
    for group in groups:
        fig.add_trace(
            go.Violin(
                x=[group] * len(data[group]),
                y=data[group],
                name=group,
                box_visible=True,
                meanline_visible=True,
                points="outliers"
            )
        )

    # Update layout
    fig.update_layout(
        title="Distribution Comparison",
        yaxis_title="Values",
        xaxis_title="Groups",
        violinmode='group'
    )

    fig
    return data, fig, go, group, groups, np


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
