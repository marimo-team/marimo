# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Distribution Plots in Altair

        Create distribution visualizations using `mark_area()` and `transform_density()`. 
        Common for comparing distributions across categories with interactive tooltips.
        """
    )
    return


@app.cell
def _():
    from vega_datasets import data
    import altair as alt

    # Load dataset
    source = data.cars()

    # Create distribution plot
    chart = alt.Chart(source).transform_density(
        'Miles_per_Gallon',
        groupby=['Origin'],
        as_=['Miles_per_Gallon', 'density']
    ).mark_area(
        opacity=0.5
    ).encode(
        x='Miles_per_Gallon:Q',
        y='density:Q',
        color='Origin:N',
        tooltip=['Origin:N', alt.Tooltip('density:Q', format='.3f')]
    ).properties(
        width=400,
        height=300,
        title='MPG Distribution by Origin'
    ).interactive()
    chart
    return alt, chart, data, source


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
