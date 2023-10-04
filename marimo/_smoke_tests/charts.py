# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.21"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    import json
    import pandas as pd
    return data, json, mo, pd


@app.cell
def __(data):
    # data
    cars = data.cars()
    employment = data.unemployment_across_industries.url
    iris = data.iris()
    return cars, employment, iris


@app.cell
def __(mo):
    chart_selection_type = mo.ui.radio(
        ["default", "point", "interval"], label="Selection Type", value="default"
    )
    theme = mo.ui.radio(
        ["default", "dark", "latimes"], label="Theme", value="default"
    )
    field_selection_type = mo.ui.radio(
        ["all", "none"], label="Legend Selection Type", value="all"
    )

    mo.hstack([chart_selection_type, field_selection_type, theme]).callout()
    return chart_selection_type, field_selection_type, theme


@app.cell
def __(chart_selection_type, field_selection_type, theme):
    import altair as alt

    alt.themes.enable(theme.value)
    chart_selection_value = (
        True
        if chart_selection_type.value == "default"
        else chart_selection_type.value
    )
    field_selection_value = field_selection_type.value == "all"
    None
    return alt, chart_selection_value, field_selection_value


@app.cell
def __(alt, cars, chart_selection_value, field_selection_value, mo):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )
    chart1 = mo.ui.chart(
        _chart.to_json(),
        chart_selection=chart_selection_value,
        field_selection=field_selection_value,
        label="Cars",
    )
    return chart1,


@app.cell
def __(mo):
    mo.md("# Basic Chart")
    return


@app.cell
def __(chart1, mo):
    mo.vstack([chart1, chart1.value.head(10)])
    return


@app.cell
def __(alt, chart_selection_value, employment, field_selection_value, mo):
    # _selection = alt.selection_point(fields=["series"], bind="legend")

    _chart = (
        alt.Chart(employment)
        .mark_area()
        .encode(
            alt.X("yearmonth(date):T").axis(domain=False, format="%Y", tickSize=0),
            alt.Y("sum(count):Q").stack("center").axis(None),
            alt.Color("series:N").scale(scheme="category20b"),
            # opacity=alt.condition(_selection, alt.value(1), alt.value(0.9)),
        )
    )
    # ).add_params(_selection)
    chart2 = mo.ui.chart(
        _chart,
        chart_selection=chart_selection_value,
        field_selection=field_selection_value,
    )
    return chart2,


@app.cell
def __(mo):
    mo.md("# Another Chart")
    return


@app.cell
def __(chart2, mo):
    mo.vstack([chart2, chart2.value.head(10)])
    return


@app.cell
def __(alt, chart_selection_value, field_selection_value, iris, mo):
    # _color_sel = alt.selection_point(fields=["species"], bind="legend")
    # _size_sel = alt.selection_point(fields=["petalWidth"], bind="legend")

    _chart = (
        alt.Chart(iris)
        .mark_circle()
        .encode(
            alt.X("sepalLength", scale=alt.Scale(zero=False)),
            alt.Y("sepalWidth", scale=alt.Scale(zero=False, padding=1)),
            color="species",
            size="petalWidth",
            # opacity=alt.condition(
            #     _color_sel & _size_sel, alt.value(1), alt.value(0.2)
            # ),
        )
        # .add_params(_color_sel, _size_sel)
    )

    chart3 = mo.ui.chart(
        _chart.to_json(),
        chart_selection=chart_selection_value,
        field_selection=field_selection_value,
    )
    return chart3,


@app.cell
def __(mo):
    mo.md("# Chart + Chart")
    return


@app.cell
def __(chart3, mo):
    mo.hstack([chart3, chart3])
    return


@app.cell
def __(mo):
    mo.md("# Chart + Table")
    return


@app.cell
def __(chart3, mo):
    mo.hstack([chart3, chart3.value.head(10)])
    return


@app.cell
def __(mo):
    mo.md("# Chart + Table returned as an array")
    return


@app.cell
def __(chart3):
    [chart3, chart3.value.head(10)]
    return


@app.cell
def __(alt, cars, chart_selection_value, field_selection_value, mo):
    brush = alt.selection_interval()
    points = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower:Q",
            y="Miles_per_Gallon:Q",
            color=alt.condition(brush, "Origin:N", alt.value("lightgray")),
        )
        .add_params(brush)
    )
    bars = (
        alt.Chart(cars)
        .mark_bar()
        .encode(y="Origin:N", color="Origin:N", x="count(Origin):Q")
        .transform_filter(brush)
    )
    plot = points & bars
    chart4 = mo.ui.chart(
        plot.to_json(),
        chart_selection=chart_selection_value,
        field_selection=field_selection_value,
    )
    return bars, brush, chart4, plot, points


@app.cell
def __(mo):
    mo.md("# Chart with transform")
    return


@app.cell
def __(chart4, mo):
    mo.vstack([chart4, chart4.value.head(10)])
    return


if __name__ == "__main__":
    app.run()
