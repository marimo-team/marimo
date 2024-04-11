# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Stacked Histogram in Altair

        If you take a standard histogram and encode another field with color, the result will be a stacked histogram:

        """
    )
    return


@app.cell
def __():
    # load an example dataset
    from vega_datasets import data

    cars = data.cars()

    # plot the dataset, referencing dataframe column names
    import altair as alt

    alt.Chart(cars).mark_bar().encode(
        x=alt.X("Miles_per_Gallon", bin=True), y="count()", color="Origin"
    )
    return alt, cars, data


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
