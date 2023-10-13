# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.24"
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
        ["default", "point", "interval"],
        label="Selection Type",
        value="default",
    )
    theme = mo.ui.radio(
        ["default", "dark", "latimes"], label="Theme", value="default"
    )
    legend_selection_type = mo.ui.radio(
        ["all", "none"], label="Legend Selection Type", value="all"
    )

    mo.hstack([chart_selection_type, legend_selection_type, theme]).callout()
    return chart_selection_type, legend_selection_type, theme


@app.cell
def __(chart_selection_type, legend_selection_type, theme):
    import altair as alt

    alt.themes.enable(theme.value)
    chart_selection_value = (
        True
        if chart_selection_type.value == "default"
        else chart_selection_type.value
    )
    legend_selection_value = legend_selection_type.value == "all"
    None
    return alt, chart_selection_value, legend_selection_value


@app.cell
def __(alt, cars, chart_selection_value, legend_selection_value, mo):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )
    chart1 = mo.ui.altair_chart(
        _chart,
        chart_selection=chart_selection_value,
        legend_selection=legend_selection_value,
        label="Cars",
    )
    return chart1,


@app.cell
def __(mo):
    mo.md("# Basic Chart")
    return


@app.cell
def __(alt, chart1, chart_selection_value, legend_selection_value, mo):
    mo.vstack(
        [
            chart1,
            mo.ui.altair_chart(
                alt.Chart(chart1.value)
                .mark_bar()
                .encode(
                    x="Origin",
                    y="count()",
                    color="Origin",
                ),
                chart_selection=chart_selection_value,
                legend_selection=legend_selection_value,
            )
            if not chart1.value.empty
            else mo.md("No selection"),
            chart1.value.head(),
        ]
    )
    return


@app.cell
def __(alt, chart_selection_value, employment, legend_selection_value, mo):
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
    chart2 = mo.ui.altair_chart(
        _chart,
        chart_selection=chart_selection_value,
        legend_selection=legend_selection_value,
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
def __(alt, chart_selection_value, iris, legend_selection_value, mo):
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

    chart3 = mo.ui.altair_chart(
        _chart,
        chart_selection=chart_selection_value,
        legend_selection=legend_selection_value,
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
def __(alt, cars, chart_selection_value, legend_selection_value, mo):
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
    chart4 = mo.ui.altair_chart(
        plot,
        chart_selection=chart_selection_value,
        legend_selection=legend_selection_value,
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


@app.cell
def __(mo):
    mo.md("# Bar chart")
    return


@app.cell
def __(alt, data, mo):
    binned = mo.ui.altair_chart(
        alt.Chart(data.cars())
        .mark_bar()
        .encode(x=alt.X("Miles_per_Gallon:Q", bin=True), y="count()")
    )
    return binned,


@app.cell
def __(alt, cars, mo):
    mean = mo.ui.altair_chart(
        alt.Chart(cars)
        .mark_bar()
        .encode(
            x="Cylinders:O",
            y="mean(Acceleration):Q",
        )
    )
    return mean,


@app.cell
def __(mean, mo):
    mo.vstack([mean, mean.value])
    return


@app.cell
def __(alt, data, mo):
    hist = (
        alt.Chart(data.cars())
        .mark_bar()
        .encode(x=alt.X("Miles_per_Gallon:Q"), y="count()")
    )
    hist = mo.ui.altair_chart(hist)
    return hist,


@app.cell
def __(hist, mo):
    mo.vstack([hist, hist.value])
    return


@app.cell
def __(mo):
    mo.md("# Pivot and horizontal bar chart")
    return


@app.cell
def __(alt, mo, pd):
    df = pd.DataFrame.from_records(
        [
            {"country": "Norway", "type": "gold", "count": 14},
            {"country": "Norway", "type": "silver", "count": 14},
            {"country": "Norway", "type": "bronze", "count": 11},
            {"country": "Germany", "type": "gold", "count": 14},
            {"country": "Germany", "type": "silver", "count": 10},
            {"country": "Germany", "type": "bronze", "count": 7},
            {"country": "Canada", "type": "gold", "count": 11},
            {"country": "Canada", "type": "silver", "count": 8},
            {"country": "Canada", "type": "bronze", "count": 10},
        ]
    )

    pivot = mo.ui.altair_chart(
        alt.Chart(df)
        .transform_pivot("type", groupby=["country"], value="count")
        .mark_bar()
        .encode(
            x="gold:Q",
            y="country:N",
        )
    )
    return df, pivot


@app.cell
def __(mo, pivot):
    mo.vstack([pivot, pivot.value.head()])
    return


@app.cell
def __(alt, data, mo):
    _source = data.population.url

    horizontal_bar = mo.ui.altair_chart(
        alt.Chart(_source)
        .mark_bar()
        .encode(
            alt.X("sum(people):Q").title("Population"),
            alt.Y("age:O"),
        )
        .transform_filter(alt.datum.year == 2000)
        .properties(height=alt.Step(20))
    )
    return horizontal_bar,


@app.cell
def __(horizontal_bar, mo):
    mo.vstack([horizontal_bar, horizontal_bar.value.head()])
    return


@app.cell
def __(alt, mo, pd):
    _source = pd.DataFrame(
        {"category": [1, 2, 3, 4, 5, 6], "value": [4, 6, 10, 3, 7, 8]}
    )

    pie = mo.ui.altair_chart(
        alt.Chart(_source)
        .mark_arc(innerRadius=50)
        .encode(
            theta="value",
            color="category:N",
        )
    )
    return pie,


@app.cell
def __(mo, pie):
    mo.vstack([pie, pie.value])
    return


if __name__ == "__main__":
    app.run()
