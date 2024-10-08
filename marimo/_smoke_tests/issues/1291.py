# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.9"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import altair as alt
    import polars as pl

    counts = pl.DataFrame(
        {
            "category": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"],
            "count": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        }
    )

    chart1 = (
        alt.Chart(counts.to_pandas())
        .encode(
            y="count",
            x=alt.X(
                "category",
            ),
        )
        .mark_bar(color="blue")
    )

    chart2 = (
        alt.Chart(counts.to_pandas())
        .encode(
            y="count",
            x=alt.X(
                "category",
            ),
        )
        .mark_bar(color="red")
    )

    mo.vstack(
        [
            chart1,
            chart2
        ]
    )
    return alt, chart1, chart2, counts, mo, pl


if __name__ == "__main__":
    app.run()
