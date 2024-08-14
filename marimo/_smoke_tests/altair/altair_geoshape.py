# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.20"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import altair as alt
    from vega_datasets import data
    import geopandas as gpd

    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    gdf_ne = gpd.read_file(url)  # zipped shapefile
    gdf_ne = gdf_ne[["NAME", "CONTINENT", "POP_EST", "geometry"]]
    return alt, data, gdf_ne, gpd, url


@app.cell
def __(gdf_ne):
    gdf_sel = gdf_ne.query("CONTINENT == 'Africa'")
    return gdf_sel,


@app.cell
def __(alt, gdf_sel):
    chart = (
        alt.Chart(gdf_sel)
        .mark_geoshape(stroke="white", strokeWidth=1.5)
        .encode(fill="NAME:N")
    )
    return chart,


@app.cell
def __(chart):
    chart
    return


@app.cell
def __(chart, mo):
    mo_chart = mo.ui.altair_chart(chart)
    mo_chart
    return mo_chart,


@app.cell
def __(mo, mo_chart):
    mo.ui.table(mo_chart.value)
    return


@app.cell
def __(chart, mo):
    mo.ui.altair_chart(chart, chart_selection=None)
    return


if __name__ == "__main__":
    app.run()
