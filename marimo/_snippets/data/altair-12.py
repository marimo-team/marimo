# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Area Charts with Gradient Fill

        Create stacked area charts using `alt.Chart().mark_area()`. Demonstrates 
        gradient fills and opacity settings with `fillOpacity`. Common for 
        visualizing time series data or part-to-whole relationships.
        """
    )
    return


@app.cell
def _():
    from vega_datasets import data
    import altair as alt
    return alt, data


@app.cell
def _(alt, data):
    def create_area_chart():
        # Load the dataset
        source = data.stocks()

        # Create area chart with gradient
        chart = alt.Chart(source).transform_filter(
            alt.datum.symbol != 'IBM'  # Remove one symbol to avoid overcrowding
        ).mark_area(
            opacity=0.7,
            interpolate='monotone'
        ).encode(
            x='date:T',
            y=alt.Y('price:Q', stack=True),
            color=alt.Color('symbol:N', legend=alt.Legend(title='Company')),
            tooltip=['date', 'price', 'symbol']
        ).properties(
            width=600,
            height=300,
            title='Stock Prices Over Time'
        ).interactive()
        
        return chart

    create_area_chart()
    return (create_area_chart,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
