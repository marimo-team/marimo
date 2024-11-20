# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "leafmap==0.41.0",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.9.20"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # Using Leafmap

        This example shows how to render a `leafmap.Map` in marimo; just output it like any other object.
        """
    )
    return


@app.cell
def __():
    import leafmap
    return (leafmap,)


@app.cell
def __(leafmap):
    m = leafmap.Map(center=(40, -100), zoom=4, height="400px")
    m.add_basemap("HYBRID")
    m.add_basemap("Esri.NatGeoWorldMap")
    m.add_tile_layer(
        url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        name="Google Satellite",
        attribution="Google",
    )
    m
    return (m,)


@app.cell
def __():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
