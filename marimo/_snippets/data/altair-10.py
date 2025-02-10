# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Box Plot with Violin Layer in Altair

        Create layered box and violin plots with Altair. Box plots display quartiles via `mark_boxplot()` 
        while violin plots show density distributions using `transform_density()`.
        Combining them reveals both summary statistics and full data distributions in a single visualization.
        """
    )
    return


@app.cell
def _():
    from vega_datasets import data
    import altair as alt

    # Load the dataset
    source = data.cars()

    # Create the base chart for the box plot
    box_plot = alt.Chart(source).mark_boxplot().encode(
        x='Origin:N',
        y=alt.Y('Horsepower:Q', title='Horsepower'),
        color='Origin:N'
    )

    # Create the violin layer
    violin = alt.Chart(source).transform_density(
        'Horsepower',
        as_=['Horsepower', 'density'],
        groupby=['Origin']
    ).mark_area(
        opacity=0.3
    ).encode(
        x='Origin:N',
        y='Horsepower:Q',
        color='Origin:N',
        fill='Origin:N'
    )

    # Combine the layers
    chart = (violin + box_plot).properties(
        width=300,
        height=300,
        title='Horsepower Distribution by Origin'
    ).interactive()
    chart
    return alt, box_plot, chart, data, source, violin


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
