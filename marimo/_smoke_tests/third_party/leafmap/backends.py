import marimo

__generated_with = "0.9.17"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __():
    import leafmap as default_leamap
    import leafmap.leafmap as leafmap
    import leafmap.foliumap as leafmap_folium
    import leafmap.plotlymap as leafmap_plotly
    return default_leamap, leafmap, leafmap_folium, leafmap_plotly


@app.cell
def __():
    import keplergl
    import leafmap.kepler as leafmap_kepler
    return keplergl, leafmap_kepler


@app.cell
def __(default_leamap):
    default_leamap.Map
    return


@app.cell
def __(leafmap):
    data = leafmap.examples.datasets.countries_geojson
    return (data,)


@app.cell
def __(data, leafmap):
    _m = leafmap.Map()
    _m.add_data(
        data,
        column="POP_EST",
        scheme="Quantiles",
        cmap="Blues",
        legend_title="Population",
    )
    _m
    return


@app.cell
def __(leafmap_plotly):
    _m = leafmap_plotly.Map(center=(40, -100), zoom=3, height=500)
    _m
    return


@app.cell
def __(data, leafmap_folium):
    _m = leafmap_folium.Map()
    _m.add_data(
        data,
        column="POP_EST",
        scheme="Quantiles",
        cmap="Blues",
        legend_title="Population",
    )
    _m
    return


@app.cell
def __(leafmap_kepler):
    _m = leafmap_kepler.Map(
        center=[40, -100], zoom=2, height=600, widescreen=False
    )
    _m
    return


if __name__ == "__main__":
    app.run()
