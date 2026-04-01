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
    base = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )
    # 1. Unit chart — width at top level, getContainerWidth works
    base.properties(width="container")
    return base, cars


@app.cell
def _(base):
    # facet — width nested under spec
    base.properties(width="container").facet(column="Origin:N")
    return


@app.cell
def _(cars):
    # with vegafusion enabled. This will use vega instead of vega-lite
    # The chart should be fully expanded
    alt.data_transformers.enable("vegafusion")

    _base = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
        .properties(width="container")
    )
    _base
    return


@app.cell
def _(base):
    # This should not stretch the entire width
    base.properties(autosize=alt.AutoSizeParams(type="fit-x"))
    return


@app.cell
def _(base):
    # Broken
    base.properties(height="container")
    return


if __name__ == "__main__":
    app.run()
