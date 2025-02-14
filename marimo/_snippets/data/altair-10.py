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
    return alt, data


@app.cell
def _(alt, data):
    def create_box_violin_plot():
        # Load the dataset
        source = data.cars()

        # Create the base chart for the box plot
        box_plot = alt.Chart(source).mark_boxplot(size=50).encode(  # Increased box size
            x=alt.X('Origin:N', axis=alt.Axis(labelFontSize=12, titleFontSize=14)),  # Larger font
            y=alt.Y('Horsepower:Q', 
                    title='Horsepower',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(labelFontSize=12, titleFontSize=14)),  # Larger font
            color=alt.Color('Origin:N', legend=alt.Legend(labelFontSize=12, titleFontSize=14))  # Larger legend
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
            width=600,  # Much larger width
            height=500,  # Much larger height
            title={
                'text': 'Horsepower Distribution by Origin',
                'fontSize': 16  # Larger title
            }
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14
        ).interactive()
        
        return chart

    create_box_violin_plot()
    return (create_box_violin_plot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
