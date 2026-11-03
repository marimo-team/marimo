import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import altair as alt
    from vega_datasets import data

    source = data.barley()
    chart = (
        alt.Chart(source)
        .mark_bar()
        .encode(
            x="year:O",
            y="sum(yield):Q",
            color="year:N",
            column="site:N",
        )
    )
    chart
    return (chart,)


@app.cell
def _(chart, mo):
    mo.ui.altair_chart(chart)


@app.cell
def _(chart):
    chart.encoding.column


@app.cell
def _(chart):
    type(chart).mro()


if __name__ == "__main__":
    app.run()
