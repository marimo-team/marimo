import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import leafmap as default_leamap
    import leafmap.leafmap as leafmap
    import leafmap.foliumap as leafmap_folium
    import leafmap.plotlymap as leafmap_plotly
    return default_leamap, leafmap, leafmap_folium, leafmap_plotly


@app.cell
def _():
    import keplergl
    import leafmap.kepler as leafmap_kepler
    return (leafmap_kepler,)


@app.cell
def _(default_leamap):
    default_leamap.Map
    return


@app.cell
def _(leafmap):
    data = leafmap.examples.datasets.countries_geojson
    return (data,)


@app.cell
def _(data, leafmap):
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
def _(leafmap_plotly):
    _m = leafmap_plotly.Map(center=(40, -100), zoom=3, height=500)
    _m
    return


@app.cell
def _(data, leafmap_folium):
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
def _(leafmap_kepler):
    _m = leafmap_kepler.Map(
        center=[40, -100], zoom=2, height=600, widescreen=False
    )
    _m
    return


if __name__ == "__main__":
    app.run()
