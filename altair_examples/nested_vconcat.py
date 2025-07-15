import marimo

__generated_with = "0.13.11"
app = marimo.App(width="medium")


@app.cell
def _():
    from vega_datasets import data
    import marimo as mo
    import altair as alt

    cars = data.cars()

    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(height=100)
    )

    stacked_chart = alt.vconcat(
        _chart,
        alt.vconcat(_chart, alt.vconcat(_chart, _chart)),
    )


    mo.ui.altair_chart(stacked_chart)
    return (stacked_chart,)


@app.cell
def _(stacked_chart):
    stacked_chart
    return


if __name__ == "__main__":
    app.run()
