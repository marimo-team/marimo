
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    import vega_datasets
    import altair as alt

    cars = vega_datasets.data.cars()

    chart = (
        alt.Chart(cars)
        .mark_text()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            text="Origin",
        )
    )

    chart = mo.ui.altair_chart(chart)
    return (chart,)


@app.cell
def _(chart, mo):
    mo.vstack([chart, chart.value.head()])
    return


if __name__ == "__main__":
    app.run()
