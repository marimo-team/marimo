# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        #  Visualization: Interactive Brushing in Altair

        With a few extra lines of code on top of a standard scatter plot, you can add selection behavior to your scatter plot. This lets you click and drag to select points.
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

    alt.Chart(cars).mark_point().encode(
        x="Horsepower",
        y="Miles_per_Gallon",
        color=alt.condition(interval, "Origin", alt.value("lightgray")),
    ).add_params(interval)
    return alt, cars, data, interval


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
