

import marimo

__generated_with = "0.13.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import pandas as pd
    import marimo as mo

    from vega_datasets import data

    source = data.cars()

    plot_1 = mo.ui.altair_chart(
        alt.Chart(source)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
        )
    )

    plot_2 = mo.ui.altair_chart(
        alt.Chart(source)
        .mark_point()
        .encode(
            x="Year",
            y="Horsepower",
        )
    )

    mo.hstack([plot_1, plot_2])
    return mo, plot_1, plot_2


@app.cell
def _(mo, plot_1, plot_2):
    mo.hstack([plot_1, plot_2], justify="start")
    return


@app.cell
def _(mo, plot_1, plot_2):
    mo.hstack([plot_1, plot_2], justify="start", widths="equal")
    return


@app.cell
def _(plot_1):
    plot_1
    return


if __name__ == "__main__":
    app.run()
