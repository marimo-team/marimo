# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    from vega_datasets import data

    return alt, data, mo


@app.cell
def _(mo):
    mo.md("""
    # Create an interactive chart

    Explore fuel economy and horsepower in the Vega cars dataset.

    Click a legend value to highlight an origin. Drag to pan and scroll to zoom.
    """)
    return


@app.cell
def _(data):
    cars = data.cars()
    return (cars,)


@app.cell
def _(alt, cars):
    origin = alt.selection_point(fields=["Origin"], bind="legend")
    chart = (
        alt.Chart(cars)
        .mark_circle(size=80)
        .encode(
            x=alt.X(
                "Horsepower:Q",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                "Miles_per_Gallon:Q",
                title="Miles per gallon",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("Origin:N", title="Origin"),
            opacity=alt.condition(
                origin,
                alt.value(0.85),
                alt.value(0.12),
            ),
            tooltip=[
                alt.Tooltip("Name:N", title="Car"),
                alt.Tooltip("Origin:N", title="Origin"),
                alt.Tooltip("Horsepower:Q", format=".0f"),
                alt.Tooltip(
                    "Miles_per_Gallon:Q",
                    title="Miles per gallon",
                    format=".1f",
                ),
            ],
        )
        .add_params(origin)
        .properties(
            height=340,
            title="Fuel economy vs. horsepower",
            width="container",
        )
        .interactive()
    )
    chart
    return


if __name__ == "__main__":
    app.run()
