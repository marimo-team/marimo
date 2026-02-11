# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
#     "plotly==5.24.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Selectable scatter map

    This example shows how to overlay a scatter plot on a map using `Plotly`, and make the plot reactive using [`mo.ui.plotly`](https://docs.marimo.io/guides/working_with_data/plotting.html#plotly) — select plots in the scatter
    plot and get them back in Python!
    """)
    return


@app.cell
def _(mo):
    import plotly.express as px

    df = px.data.carshare()
    fig = mo.ui.plotly(px.scatter_mapbox(
        df,
        lat="centroid_lat",
        lon="centroid_lon",
        color="peak_hour",
        size="car_hours",
        color_continuous_scale=px.colors.cyclical.IceFire,
        size_max=10,
        zoom=10,
        mapbox_style="carto-positron",
    ))
    return (fig,)


@app.cell
def _(fig, mo):
    mo.hstack([fig, fig.value], justify="start")
    return


if __name__ == "__main__":
    app.run()
