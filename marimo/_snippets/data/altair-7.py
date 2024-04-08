# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Linked Scatter-Plot and Histogram in Altair

        Altair selections can be used for a variety of things. This example shows a scatter plot and a histogram with selections over both that allow exploring the relationships between points
        """
    )
    return


@app.cell
def __():
    # load an example dataset
    from vega_datasets import data

    cars = data.cars()

    import altair as alt

    interval = alt.selection_interval()

    points = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color=alt.condition(interval, "Origin", alt.value("lightgray")),
        )
        .add_params(interval)
    )

    histogram = (
        alt.Chart(cars)
        .mark_bar()
        .encode(x="count()", y="Origin", color="Origin")
        .transform_filter(interval)
    )

    points & histogram
    return alt, cars, data, histogram, interval, points


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
