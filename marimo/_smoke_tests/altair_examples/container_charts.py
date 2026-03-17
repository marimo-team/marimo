import marimo

__generated_with = "0.21.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import altair as alt
    from altair.datasets import data

    return alt, data


@app.cell
def _(alt, data):
    cars = data.cars()

    # make the chart
    chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .interactive()
    )
    chart.properties(width="container")
    return (chart,)


@app.cell
def _(chart):
    # Broken
    chart.properties(height="container")
    return


if __name__ == "__main__":
    app.run()
