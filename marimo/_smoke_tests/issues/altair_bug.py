# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import altair as alt
    from vega_datasets import data
    return alt, data, mo


@app.cell
def _(alt, data, mo):
    source = data.seattle_weather()

    bar = (
        alt.Chart(source)
        .mark_bar(cornerRadius=10, height=10)
        .encode(
            x=alt.X("min(temp_min):Q")
            .scale(domain=[-15, 45])
            .title("Temperature (°C)"),
            x2="max(temp_max):Q",
            y=alt.Y("month(date):O").title(None),
        )
    )

    text_min = (
        alt.Chart(source)
        .mark_text(align="right", dx=-5)
        .encode(
            x="min(temp_min):Q", y=alt.Y("month(date):O"), text="min(temp_min):Q"
        )
    )

    text_max = (
        alt.Chart(source)
        .mark_text(align="left", dx=5)
        .encode(
            x="max(temp_max):Q", y=alt.Y("month(date):O"), text="max(temp_max):Q"
        )
    )

    _chart = (bar + text_min + text_max).properties(
        title=alt.Title(
            text="Temperature variation by month",
            subtitle="Seatle weather, 2012-2015",
        )
    )
    # Bug: chart_selection does not work when not false
    # This is due to month(date) being an aggregatation that we cannot back out.
    chart = mo.ui.altair_chart(_chart, chart_selection=False)
    return (chart,)


@app.cell
def _(chart):
    chart
    return


@app.cell
def _(chart):
    chart.selections
    return


@app.cell
def _(chart):
    chart.value
    return


@app.cell
def _(chart):
    chart.dataframe
    return


if __name__ == "__main__":
    app.run()
