import marimo

__generated_with = "0.1.19"
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
    selection_type = mo.ui.radio(
        ["point", "interval", "None"], label="Selection Type:", value="interval"
    )
    theme = mo.ui.radio(
        ["default", "dark", "latimes"], label="Theme:", value="default"
    )

    mo.hstack([selection_type, theme]).left()
    return selection_type, theme


@app.cell
def __(theme):
    import altair as alt

    alt.themes.enable(theme.value)
    return alt,


@app.cell
def __(alt, cars, mo, selection_type):
    _chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )
    chart1 = mo.ui.vega(
        _chart.to_json(),
        selection_chart=selection_type.value
        if selection_type.value != "None"
        else None,
        selection_fields=False,
        label="Cars",
    )
    return chart1,


@app.cell
def __(chart1, mo):
    mo.vstack([chart1, chart1.value.head(10)])
    return


@app.cell
def __(alt, employment, mo):
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
    chart2 = mo.ui.vega(_chart.to_json())
    return chart2,


@app.cell
def __(chart2, mo):
    mo.vstack([chart2, chart2.value.head(10)])
    return


@app.cell
def __(alt, iris, mo):
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

    chart3 = mo.ui.vega(_chart.to_json())
    return chart3,


@app.cell
def __(chart3, mo):
    mo.hstack([chart3, chart3])
    return


@app.cell
def __(chart3, mo):
    # TODO: hstack does not look great with a resizing chart and fixed table. how can we make this good out of the box?
    mo.hstack([chart3, chart3.value.head(10)])
    return


@app.cell
def __(chart3):
    # TODO: this also looks bad
    [chart3, chart3.value.head(1)]
    return


if __name__ == "__main__":
    app.run()
