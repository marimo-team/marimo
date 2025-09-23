import marimo

__generated_with = "0.16.0"
app = marimo.App(
    width="medium",
    layout_file="layouts/centered_slides.slides.json",
)


@app.cell
def _():
    import marimo as mo

    mo.iframe("https://marimo.io/")
    return (mo,)


@app.cell
def _(mo):
    mo.iframe("https://marimo.io/", height="600px")
    return


@app.cell
def _(mo):
    mo.hstack(
        [mo.iframe("https://marimo.io/"), mo.iframe("https://marimo.io/")],
        widths="equal",
    )
    return


@app.cell
def _(mo):
    mo.vstack([mo.iframe("https://marimo.io/"), mo.iframe("https://marimo.io/")])
    return


@app.cell
def _():
    import altair as alt
    import polars as pl

    df = pl.read_parquet(
        "https://github.com/uwdata/mosaic/raw/main/data/athletes.parquet"
    )
    df

    df.plot.bar("sport", "count()", color="sex").properties(height=400)
    return


@app.cell
def _(mo):
    import plotly.express as px

    _df = px.data.gapminder().query("country=='Germany'")
    fig = px.line(_df, x="year", y="lifeExp", title="Life expectancy in Germany")

    mo.ui.plotly(fig)
    return (fig,)


@app.cell
def _(fig, mo):
    mo.vstack([mo.md("## Chart with a title"), mo.ui.plotly(fig)])
    return


if __name__ == "__main__":
    app.run()
