# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Linked Brushing in Altair

        If you apply the same selection to multiple panels of an Altair chart, the selections will be linked:
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

    base = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            y="Miles_per_Gallon",
            color=alt.condition(interval, "Origin", alt.value("lightgray")),
        )
        .add_params(interval)
    )

    base.encode(x="Acceleration") | base.encode(x="Horsepower")
    return alt, base, cars, data, interval


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
