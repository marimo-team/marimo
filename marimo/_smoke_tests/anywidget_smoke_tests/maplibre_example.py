# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "maplibre",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import functools
    return (mo,)


@app.cell
def _():
    from maplibre.controls import NavigationControl, ScaleControl
    from maplibre.ipywidget import MapOptions, MapWidget
    return MapOptions, MapWidget, NavigationControl, ScaleControl


@app.cell
def _():
    deck_grid_layer = {
        "@@type": "GridLayer",
        "id": "GridLayer",
        "data": "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/sf-bike-parking.json",
        "extruded": True,
        "getPosition": "@@=COORDINATES",
        "getColorWeight": "@@=SPACES",
        "getElevationWeight": "@@=SPACES",
        "elevationScale": 4,
        "cellSize": 200,
        "pickable": True,
    }
    return (deck_grid_layer,)


@app.cell
def _(MapOptions):
    map_options = MapOptions(
        center=(-122.4, 37.74),
        zoom=12,
        hash=True,
        pitch=40,
    )
    return (map_options,)


@app.cell
def _(MapWidget, NavigationControl, deck_grid_layer, map_options, mo):
    m = MapWidget(map_options)
    m.use_message_queue(False)
    m.add_control(NavigationControl())
    m.add_deck_layers([deck_grid_layer])
    m = mo.ui.anywidget(m)
    m
    return (m,)


@app.cell
def _(mo):
    add_control_button = mo.ui.run_button(label="add scale control")
    add_control_button
    return (add_control_button,)


@app.cell
def _(ScaleControl, add_control_button, m):
    if add_control_button.value:
        m.add_control(ScaleControl())
    return


@app.cell
def _(m):
    m.clicked
    return


@app.cell
def _(m):
    m.center
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
