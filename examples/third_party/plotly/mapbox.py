import marimo

__generated_with = "0.1.51"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """# Mapping Example

    This example uses <a href="https://plotly.com/python/scattermapbox/" target="_blank">Mapbox</a> in `plotly.express` to build a scatter plot on a street map. The switch enables the satellite view.
    """
    )
    return


@app.cell
def __(mo):
    view_button = mo.ui.switch(value=False)
    mo.hstack([mo.md("Satellite view:"), view_button], justify="start")
    return view_button,


@app.cell
def __(mo, get_map, view_button):
    f = mo.ui.plotly(get_map(satellite=view_button.value))
    f
    return f,

@app.cell
def __(f, mo):
    mo.ui.table(f.value)
    return


@app.cell
def __(px, us_cities):
    def get_map(satellite):
        map = px.scatter_mapbox(
            us_cities,
            lat="lat",
            lon="lon",
            hover_name="City",
            hover_data=["State", "Population"],
            color_discrete_sequence=["fuchsia"],
            zoom=3,
            height=300,
        )
        if satellite:
            map.update_layout(
                mapbox_style="white-bg",
                mapbox_layers=[
                    {
                        "below": "traces",
                        "sourcetype": "raster",
                        "sourceattribution": "United States Geological Survey",
                        "source": [
                            "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"
                        ],
                    }
                ],
            )
            map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        else:
            map.update_layout(mapbox_style="open-street-map")
            map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        return map
    return get_map,


@app.cell
def __(pd):
    us_cities = pd.read_csv(
        "https://raw.githubusercontent.com/plotly/datasets/master/us-cities-top-1k.csv"
    )
    return us_cities,


@app.cell
def __():
    import os
    import sys

    import pandas as pd
    import plotly.express as px

    import marimo as mo
    return mo, os, pd, px, sys


if __name__ == "__main__":
    app.run()
