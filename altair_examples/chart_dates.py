import marimo

__generated_with = "0.11.30"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import polars as pl
    import altair as alt
    from datetime import date
    return alt, date, pl


@app.cell
def _(date, pl):
    df = pl.DataFrame({"x": [date(2025, 1, 1)], "y": [1.0]})
    return (df,)


@app.cell
def _(alt, df):
    chart = alt.Chart(df).mark_bar().encode(x="x:T", y="y:Q")
    chart
    return (chart,)


@app.cell
def _(chart, mo):
    mo.ui.altair_chart(chart)
    return


@app.cell
def _(alt, chart, mo):
    with alt.data_transformers.enable("marimo_csv"):
        mo.output.append(chart)
    return


@app.cell
def _(alt, chart, mo):
    with alt.data_transformers.enable("marimo_json"):
        mo.output.append(chart)
    return


if __name__ == "__main__":
    app.run()
