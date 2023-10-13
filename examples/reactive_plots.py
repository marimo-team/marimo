import marimo

__generated_with = "0.1.29"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md("# Welcome to marimo!")
    return


@app.cell
def __(bars, mo, scatter):
    chart = mo.ui.altair_chart(scatter & bars)
    chart
    return chart,


@app.cell
def __(chart, mo):
    (filtered_data := mo.ui.table(chart.value))
    return filtered_data,


@app.cell
def __(alt, filtered_data, mo):
    mo.stop(not len(filtered_data.value))
    mpg_hist = mo.ui.altair_chart(
        alt.Chart(filtered_data.value)
        .mark_bar()
        .encode(alt.X("Miles_per_Gallon:Q", bin=True), y="count()")
    )
    horsepower_hist = mo.ui.altair_chart(
        alt.Chart(filtered_data.value)
        .mark_bar()
        .encode(alt.X("Horsepower:Q", bin=True), y="count()")
    )
    mo.hstack([mpg_hist, horsepower_hist], justify="space-around", widths="equal")
    return horsepower_hist, mpg_hist


@app.cell
def __(alt, data):
    cars = data.cars()
    brush = alt.selection_interval()
    scatter = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .add_params(brush)
    )
    bars = (
        alt.Chart(cars)
        .mark_bar()
        .encode(y="Origin:N", color="Origin:N", x="count(Origin):Q")
        .transform_filter(brush)
    )
    return bars, brush, cars, scatter


@app.cell
def __():
    import altair as alt
    from vega_datasets import data
    return alt, data


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
