# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt

    alt.data_transformers.enable("marimo_csv")

    test_data = pl.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "David"],
            "salary": [50000, 60000, 75000, 55000],
        }
    )


    chart = (
        alt.Chart(test_data.to_pandas())
        .encode(
            y="salary",
            x="name",
        )
        .mark_point(color="red")
    )
    chart
    return chart, mo


@app.cell
def _(chart, mo):
    mo.ui.altair_chart(chart)
    return


if __name__ == "__main__":
    app.run()
