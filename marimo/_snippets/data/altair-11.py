# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Faceted Charts in Altair

        Faceted charts split your data into multiple views based on categories, making it easy to spot patterns and compare groups. 
        Built with Altair's `facet()` method and includes interactive zoom/pan controls via `.interactive()`.
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
    def create_faceted_chart():
        # Load the dataset
        source = data.cars()

        # Create interactive base scatter plot
        base = alt.Chart(source).mark_point().encode(
            x='Horsepower:Q',
            y='Miles_per_Gallon:Q',
            color='Origin:N',
            tooltip=['Name', 'Origin', 'Horsepower', 'Miles_per_Gallon']
        ).properties(
            width=180,
            height=180
        ).interactive()  # Make base chart interactive

        # Create faceted chart
        chart = base.facet(
            column='Cylinders:O',
            title='Miles per Gallon vs. Horsepower by # Cylinders'
        ).configure_header(
            labelFontSize=12,
            titleFontSize=14
        ).configure_title(
            fontSize=16
        )
        
        return chart

    create_faceted_chart()
    return (create_faceted_chart,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
