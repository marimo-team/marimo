# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "polars==1.17.1",
#     "marimo",
#     "quak==0.2.1",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import quak

    return mo, pl, quak


@app.cell
def _(mo, pl, quak):
    df = pl.read_csv(
        "https://raw.githubusercontent.com/uwdata/mosaic/main/data/athletes.csv"
    )
    widget = mo.ui.anywidget(quak.Widget(df))
    widget
    return (widget,)


@app.cell
def _(grouped_selection, mo):
    import altair as alt


    mo.ui.altair_chart(
        alt.Chart(grouped_selection)
        .mark_bar()
        .encode(y=alt.Y("nationality:N").sort("-x"), x="count:Q")
        .transform_window(
            rank="rank(count)", sort=[alt.SortField("count", order="descending")]
        )
        .transform_filter(alt.datum.rank < 10)
        .properties(height=400)
    )
    return


@app.cell
def _(widget):
    selection = widget.data().df()
    return (selection,)


@app.cell
def _(selection):
    selection["count"] = 1
    grouped_selection = (
        selection[["nationality", "count"]]
        .groupby(["nationality"])
        .agg("count")
        .reset_index()
    )
    return (grouped_selection,)


if __name__ == "__main__":
    app.run()
