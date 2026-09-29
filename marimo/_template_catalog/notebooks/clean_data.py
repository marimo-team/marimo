# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


@app.cell
def _(pl):
    raw_sales = pl.DataFrame(
        {
            "product": ["Notebook", "Pen set", "Desk pad", "Notebook"],
            "units": [12, None, 15, 18],
            "unit_price": [19.0, 12.0, None, 18.5],
        }
    )
    return (raw_sales,)


@app.cell
def _(pl, raw_sales):
    clean_sales = raw_sales.with_columns(
        pl.col("units").fill_null(0),
        pl.col("unit_price").fill_null(pl.col("unit_price").median()),
    ).with_columns(
        (pl.col("units") * pl.col("unit_price")).alias("revenue")
    )
    return (clean_sales,)


@app.cell
def _(clean_sales, mo, raw_sales):
    mo.vstack(
        [
            mo.md("# Clean and transform data"),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("## Before"),
                            mo.ui.table(raw_sales, selection=None),
                        ]
                    ),
                    mo.vstack(
                        [
                            mo.md("## After"),
                            mo.ui.table(clean_sales, selection=None),
                        ]
                    ),
                ],
                widths="equal",
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
