# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Basic Text""")
    return


@app.cell
def _(mo):
    import altair as alt
    from vega_datasets import data

    chart = (
        alt.Chart(data.cars())
        .mark_text()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            text="Origin",
        )
    )

    chart = mo.ui.altair_chart(chart)
    return alt, chart, data


@app.cell
def _(chart, mo):
    mo.vstack([chart, chart.value.head()])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Bar chart with text""")
    return


@app.cell(hide_code=True)
def _(alt, data, mo):
    _source = data.barley()

    bars = (
        alt.Chart(_source)
        .mark_bar()
        .encode(
            x=alt.X("sum(yield):Q").stack("zero"),
            y=alt.Y("variety:N"),
            color=alt.Color("site"),
        )
    )

    text = (
        alt.Chart(_source)
        .mark_text(dx=-15, dy=3, color="white")
        .encode(
            x=alt.X("sum(yield):Q").stack("zero"),
            y=alt.Y("variety:N"),
            detail="site:N",
            text=alt.Text("sum(yield):Q", format=".1f"),
        )
    )

    chart2 = mo.ui.altair_chart(bars + text)
    chart2
    return (chart2,)


@app.cell
def _(chart2):
    chart2.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Bar chart with double text

        This fails for another reason which is that `month(date)` field gets converted into `month_date` and breaks the backend filtering.
        """
    )
    return


@app.cell(hide_code=True)
def _(alt, data, mo):
    _source = data.seattle_weather()

    bar = (
        alt.Chart(_source)
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
        alt.Chart(_source)
        .mark_text(align="right", dx=-5)
        .encode(
            x="min(temp_min):Q",
            y=alt.Y("month(date):O"),
            text="min(temp_min):Q",
        )
    )

    text_max = (
        alt.Chart(_source)
        .mark_text(align="left", dx=5)
        .encode(
            x="max(temp_max):Q",
            y=alt.Y("month(date):O"),
            text="max(temp_max):Q",
        )
    )

    _chart = (bar + text_min + text_max).properties(
        title=alt.Title(
            text="Temperature variation by month",
            subtitle="Seatle weather, 2012-2015",
        )
    )

    chart3 = mo.ui.altair_chart(_chart)
    chart3
    return (chart3,)


@app.cell
def _(chart3):
    chart3.selections
    return


if __name__ == "__main__":
    app.run()
