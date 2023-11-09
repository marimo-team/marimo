import marimo

__generated_with = "0.1.47"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Plotly Express Mapbox")
    return


@app.cell
def __(px, us_cities):
    fig = px.scatter_mapbox(
        us_cities,
        lat="lat",
        lon="lon",
        hover_name="City",
        hover_data=["State", "Population"],
        color_discrete_sequence=["fuchsia"],
        zoom=3,
        height=300,
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig
    return fig,


@app.cell
def __(pd):
    us_cities = pd.read_csv(
        "https://raw.githubusercontent.com/plotly/datasets/master/us-cities-top-1k.csv"
    )
    return us_cities,


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import plotly.express as px
    return mo, pd, px


if __name__ == "__main__":
    app.run()
