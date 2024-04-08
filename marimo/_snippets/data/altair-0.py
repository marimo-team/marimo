# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Interactive Scatter Plot in Altair

        Altair lets you easily create an interactive scatter plot from data stored in a Pandas dataframe.
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

    (
        alt.Chart(cars)
        .mark_point()
        .encode(x="Horsepower", y="Miles_per_Gallon", color="Origin")
        .interactive()
    )
    return alt, cars, data


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
