# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Multi-View Dashboard in Altair

        Create interactive dashboards using `alt.vconcat()` and `alt.hconcat()`. 
        Demonstrates linked views with `alt.selection()` for cross-filtering data.
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
    def create_dashboard():
        # Load dataset
        source = data.cars()

        # Create selection that links all views
        brush = alt.selection_interval(name='select')

        # Scatter plot
        scatter = alt.Chart(source).mark_point().encode(
            x='Horsepower:Q',
            y='Miles_per_Gallon:Q',
            color=alt.condition(brush, 'Origin:N', alt.value('lightgray'))
        ).properties(
            width=300,
            height=200
        ).add_params(brush)

        # Histogram
        hist = alt.Chart(source).mark_bar().encode(
            x='Miles_per_Gallon:Q',
            y='count()',
            color='Origin:N'
        ).transform_filter(
            brush
        ).properties(
            width=300,
            height=100
        )

        # Combine views
        chart = alt.hconcat(scatter, hist)

        return chart

    create_dashboard()
    return (create_dashboard,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
