# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Geographic Choropleth Map

        Create an interactive choropleth map for geographic data visualization.
        Common usage: `fig = px.choropleth(df, locations='iso_code', color='values')`.
        """
    )
    return


@app.cell
def _():
    import plotly.express as px
    import pandas as pd

    # Sample data for countries
    data = {
        'country_code': ['USA', 'GBR', 'FRA', 'DEU', 'JPN', 'IND', 'CHN'],
        'value': [100, 30, 50, 76, 61, 89, 95],
        'text': ['United States', 'United Kingdom', 'France', 
                'Germany', 'Japan', 'India', 'China']
    }
    df = pd.DataFrame(data)

    # Create choropleth map
    fig = px.choropleth(
        df,
        locations='country_code',
        color='value',
        hover_name='text',
        color_continuous_scale='Viridis',
        title='Global Distribution Map',
        locationmode='ISO-3'
    )

    # Update layout
    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='equirectangular'
        ),
        height=600
    )

    fig
    return data, df, fig, pd, px


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
