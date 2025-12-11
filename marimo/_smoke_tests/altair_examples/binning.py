# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "numpy",
#     "vega-datasets",
#     "altair",
#     "pyarrow==22.0.0",
#     "polars==1.34.0",
# ]
# ///

import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Binning Examples""")
    return


@app.cell
def _():
    import altair as alt
    import numpy as np
    import pandas as pd
    import polars as pl
    import pyarrow
    from vega_datasets import data
    return alt, data, pl


@app.cell
def _(data, pl):
    # Load datasets
    movies = pl.DataFrame(data.movies().drop(columns=["Title"]))
    cars = pl.DataFrame(data.cars())
    return cars, movies


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Basic Histogram with Auto-binning""")
    return


@app.cell
def _(alt, mo, movies):
    # Simple histogram with automatic binning
    basic_histogram = mo.ui.altair_chart(
        alt.Chart(movies.head(100))
        .mark_bar()
        .encode(
            x=alt.X("IMDB_Rating:Q", bin=True, title="IMDB Rating"),
            y=alt.Y("count()", title="Count of Movies"),
        )
        .properties(
            width="container", height=300, title="Distribution of IMDB Ratings"
        ),
    )
    basic_histogram
    return (basic_histogram,)


@app.cell
def _(basic_histogram, mo):
    mo.vstack([basic_histogram.value])
    return


@app.cell
def _():
    # basic_histogram.selections
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Histogram with Custom Bin Parameters""")
    return


@app.cell
def _(alt, cars, mo):
    # Histogram with custom maxbins parameter
    custom_bins = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_bar()
        .encode(
            x=alt.X(
                "Miles_per_Gallon:Q",
                bin=alt.Bin(maxbins=20),
                title="Miles per Gallon",
            ),
            y=alt.Y("count()", title="Count"),
        )
        .properties(
            width="container", height=300, title="MPG Distribution (20 bins max)"
        )
    )
    custom_bins
    return (custom_bins,)


@app.cell
def _(custom_bins, mo):
    mo.vstack([custom_bins.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Histogram with Fixed Bin Step""")
    return


@app.cell
def _(alt, cars, mo):
    # Histogram with fixed step size
    step_bins = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_bar()
        .encode(
            x=alt.X(
                "Horsepower:Q",
                bin=alt.Bin(step=25),
                title="Horsepower",
            ),
            y=alt.Y("count()", title="Count"),
        )
        .properties(width="container", height=300, title="Horsepower (bins of 25)")
    )
    step_bins
    return (step_bins,)


@app.cell
def _(mo, step_bins):
    mo.vstack([step_bins.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## 2D Binning (Heatmap)""")
    return


@app.cell
def _(alt, mo, movies):
    # 2D histogram using rect mark
    heatmap = mo.ui.altair_chart(
        alt.Chart(movies)
        .mark_rect()
        .encode(
            x=alt.X("IMDB_Rating:Q", bin=alt.Bin(maxbins=10), title="IMDB Rating"),
            y=alt.Y(
                "Rotten_Tomatoes_Rating:Q",
                bin=alt.Bin(maxbins=10),
                title="Rotten Tomatoes Rating",
            ),
            color=alt.Color("count()", scale=alt.Scale(scheme="viridis")),
        )
        .properties(
            width="container",
            height=300,
            title="2D Distribution of Movie Ratings",
        )
    )
    heatmap
    return (heatmap,)


@app.cell
def _(heatmap, mo):
    mo.vstack([heatmap.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Binned Color Encoding""")
    return


@app.cell
def _(alt, cars, mo):
    # Scatter plot with binned color encoding
    binned_color = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_circle(size=60)
        .encode(
            x=alt.X("Horsepower:Q", title="Horsepower"),
            y=alt.Y("Miles_per_Gallon:Q", title="MPG"),
            color=alt.Color(
                "Acceleration:Q",
                bin=alt.Bin(maxbins=5),
                title="Acceleration (binned)",
            ),
        )
        .properties(
            width="container",
            height=400,
            title="Car Performance with Binned Acceleration",
        )
    )
    binned_color
    return (binned_color,)


@app.cell
def _(binned_color, mo):
    mo.vstack([binned_color.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Binned Size Encoding""")
    return


@app.cell
def _(alt, cars, mo):
    # Scatter plot with binned size encoding
    binned_size = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_point()
        .encode(
            x=alt.X("Horsepower:Q", title="Horsepower"),
            y=alt.Y("Miles_per_Gallon:Q", title="MPG"),
            size=alt.Size(
                "Displacement:Q",
                bin=alt.Bin(maxbins=4),
                title="Displacement (binned)",
            ),
            color=alt.Color("Origin:N"),
        )
        .properties(
            width="container",
            height=400,
            title="Car Performance with Binned Displacement",
        )
    )
    binned_size
    return (binned_size,)


@app.cell
def _(binned_size, mo):
    mo.vstack([binned_size.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Stacked Histogram with Binning""")
    return


@app.cell
def _(alt, cars, mo):
    # Stacked histogram showing distribution by origin
    stacked_histogram = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_bar()
        .encode(
            x=alt.X("Horsepower:Q", bin=alt.Bin(maxbins=15), title="Horsepower"),
            y=alt.Y("count()", title="Count"),
            color=alt.Color("Origin:N", title="Origin"),
        )
        .properties(
            width="container",
            height=300,
            title="Horsepower Distribution by Origin",
        )
    )
    stacked_histogram
    return (stacked_histogram,)


@app.cell
def _(mo, stacked_histogram):
    mo.vstack([stacked_histogram.value])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Binning with Selection""")
    return


@app.cell
def _(alt, mo, movies):
    # Interactive histogram with selection
    binned_selection = mo.ui.altair_chart(
        alt.Chart(movies)
        .mark_bar()
        .encode(
            x=alt.X("IMDB_Rating:Q", bin=True, title="IMDB Rating"),
            y=alt.Y("count()", title="Count"),
        )
        .properties(
            width="container",
            height=300,
            title="IMDB Rating Distribution (Interactive)",
        ),
        chart_selection="interval",
    )
    binned_selection
    return (binned_selection,)


@app.cell
def _(binned_selection, mo):
    mo.vstack([binned_selection.value, binned_selection.selections])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Custom Bin Extent""")
    return


@app.cell
def _(alt, cars, mo):
    # Histogram with custom extent (min and max range)
    extent_bins = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_bar()
        .encode(
            x=alt.X(
                "Miles_per_Gallon:Q",
                bin=alt.Bin(extent=[10, 50], step=5),
                title="Miles per Gallon",
            ),
            y=alt.Y("count()", title="Count"),
        )
        .properties(
            width="container",
            height=300,
            title="MPG Distribution (10-50 range, step of 5)",
        )
    )
    extent_bins
    return (extent_bins,)


@app.cell
def _(extent_bins, mo):
    mo.vstack([extent_bins.value])
    return


if __name__ == "__main__":
    app.run()
