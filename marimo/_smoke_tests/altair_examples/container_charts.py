import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import altair as alt
    from altair.datasets import data


@app.cell
def _():
    cars = data.cars()

    chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .interactive()
        .properties(width="container")
    )
    mo.hstack([chart, chart.configure_axis(grid=False)], widths="equal")
    return (chart,)


@app.cell
def _(chart):
    # Broken
    chart.properties(height="container")
    return


if __name__ == "__main__":
    app.run()
