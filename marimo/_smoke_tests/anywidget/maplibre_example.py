# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "maplibre",
# ]
# ///

import marimo

__generated_with = "0.8.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import functools
    return functools, mo


@app.cell
def __():
    from maplibre.controls import NavigationControl, ScaleControl
    from maplibre.ipywidget import MapOptions, MapWidget
    return MapOptions, MapWidget, NavigationControl, ScaleControl


@app.cell
def __():
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
    return deck_grid_layer,


@app.cell
def __(MapOptions):
    map_options = MapOptions(
        center=(-122.4, 37.74),
        zoom=12,
        hash=True,
        pitch=40,
    )
    return map_options,


@app.cell
def __(MapWidget, NavigationControl, deck_grid_layer, map_options, mo):
    m = MapWidget(map_options)
    m.use_message_queue(False)
    m.add_control(NavigationControl())
    m.add_deck_layers([deck_grid_layer])
    m = mo.ui.anywidget(m)
    m
    return m,


@app.cell
def __(mo):
    add_control_button = mo.ui.run_button(label="add scale control")
    add_control_button
    return add_control_button,


@app.cell
def __(ScaleControl, add_control_button, m):
    if add_control_button.value:
        m.add_control(ScaleControl())
    return


@app.cell
def __(m):
    m.clicked
    return


@app.cell
def __(m):
    m.zoom
    return


@app.cell
def __(m):
    m.center
    return


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
