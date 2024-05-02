# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.7"
app = marimo.App()


@app.cell
def __():
    import altair as alt
    import polars as pl
    alt.data_transformers.enable("marimo_csv")

    counts = pl.DataFrame(
        {
            "category": ["A", "D", "E", "G", "M", "A1", "A2", "G1", "G2", "G3", "G4"],
            "count": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110],
        }
    )

    (
        alt.Chart(counts.to_pandas())
        .encode(
            y="count",
            x=alt.X(
                "category",
            ),
        )
        .mark_bar()
    )
    return alt, counts, pl


if __name__ == "__main__":
    app.run()
