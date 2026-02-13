# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Animated Bubble Chart

        Create an animated bubble chart for time-series multi-dimensional data.
        Common usage: `px.scatter(df, x='x', y='y', animation_frame='year', size='size')`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import pandas as pd
    import numpy as np

    # Generate sample time-series data
    np.random.seed(42)
    years = range(2015, 2024)
    categories = ['A', 'B', 'C', 'D']

    data = []
    for year in years:
        for cat in categories:
            data.append({
                'year': year,
                'category': cat,
                'value_x': np.random.normal(loc=year-2015, scale=1),
                'value_y': np.random.normal(loc=5, scale=2),
                'size': np.random.randint(20, 100),
                'growth': np.random.uniform(-10, 20)
            })

    df = pd.DataFrame(data)

    # Create animated bubble chart
    fig = px.scatter(
        df,
        x='value_x',
        y='value_y',
        animation_frame='year',
        size='size',
        color='category',
        hover_name='category',
        text='category',
        size_max=60,
        range_x=[-1, 10],
        range_y=[-5, 15],
        title='Metric Evolution Over Time'
    )

    # Update layout
    fig.update_traces(
        textposition='top center',
        marker=dict(sizemin=10)
    )

    fig.update_layout(
        height=600,
        showlegend=True
    )

    fig
    return cat, categories, data, df, fig, np, pd, px, year, years


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
