import marimo

__generated_with = "0.11.18"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""This is some experimental work to see if we can pre-aggregate column charts on the backend for performance. We are trying to use the dataframe of choice, to avoid additional dependencies.""")
    return


@app.cell(hide_code=True)
def _(pl):
    df = pl.read_csv("hf://datasets/scikit-learn/Fish/Fish.csv")
    df
    return (df,)


@app.cell(hide_code=True)
def _(alt, charts, mo):
    _charts = []
    for _col, data in charts.items():
        chart = mo.ui.altair_chart(
            alt.Chart(alt.Data(values=data))
            .mark_bar()
            .encode(
                x=alt.X("breakpoint:Q", bin=alt.Bin(maxbins=10), title=f"{_col}"),
                y="count:Q",
            )
            .properties(title=f"Histogram of {_col}"),
            chart_selection=None,
            legend_selection=None,
        )
        _charts.append(chart)
    mo.hstack(_charts)
    return chart, data


@app.cell
def _(df, pl):
    charts = {}
    for col in df.columns:
        if df[col].dtype in [pl.datatypes.Float64, pl.datatypes.Int64]:
            hist_data = df[col].hist().to_dicts()
            charts[col] = hist_data

    charts.keys()
    return charts, col, hist_data


@app.cell
def _(df):
    res = df["Weight"].hist().to_dicts()
    res[0]
    return (res,)


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt
    return alt, mo, pl


if __name__ == "__main__":
    app.run()
