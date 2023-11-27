import marimo

__generated_with = "0.1.59"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        f"""
    # Leafmap + marimo

    To get started, install **[leafmap](https://leafmap.org/)**:

    ```
    pip install leafmap marimo
    ```
    """
    )
    return


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
    return m,


@app.cell
def __():
    import marimo as mo
    import leafmap
    return leafmap, mo


if __name__ == "__main__":
    app.run()
