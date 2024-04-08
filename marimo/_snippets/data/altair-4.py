# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Scatter Plot with Rolling Mean in Altair

        This shows a scatter chart of miles per gallon as a function of year, with lines indicating the mean values for each country within the given year.
        """
    )
    return


@app.cell
def __():
    # load an example dataset
    from vega_datasets import data

    cars = data.cars()

    import altair as alt

    points = (
        alt.Chart(cars)
        .mark_point()
        .encode(x="Year:T", y="Miles_per_Gallon", color="Origin")
        .properties(width=800)
    )

    lines = (
        alt.Chart(cars)
        .mark_line()
        .encode(x="Year:T", y="mean(Miles_per_Gallon)", color="Origin")
        .properties(width=800)
        .interactive(bind_y=False)
    )

    points + lines
    return alt, cars, data, lines, points


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
