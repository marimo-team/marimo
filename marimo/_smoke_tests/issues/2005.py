# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.19"
app = marimo.App(width="medium")


@app.cell
def __():
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
    return alt, chart, mo, pl, test_data


@app.cell
def __(chart, mo):
    mo.ui.altair_chart(chart)
    return


if __name__ == "__main__":
    app.run()
