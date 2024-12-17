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

__generated_with = "0.8.2"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import quak
    return mo, pl, quak


@app.cell
def __(mo, pl, quak):
    df = pl.read_parquet("https://github.com/uwdata/mosaic/raw/main/data/athletes.parquet")
    widget = mo.ui.anywidget(quak.Widget(df))
    widget
    return df, widget


@app.cell
def __(grouped_selection, mo):
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
    return alt,


@app.cell
def __(widget):
    selection = widget.data().df()
    return selection,


@app.cell
def __(selection):
    selection["count"] = 1
    grouped_selection = selection[["nationality", "count"]].groupby(["nationality"]).agg("count").reset_index()
    return grouped_selection,


if __name__ == "__main__":
    app.run()
