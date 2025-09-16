import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    from datetime import date

    df = (
        pl.date_range(date(2001, 1, 1), date(2001, 1, 3), eager=True)
        .alias("date")
        .to_frame()
    )
    df.with_columns(
        pl.col("date").dt.timestamp().alias("timestamp_us"),
        pl.col("date").dt.timestamp("ms").alias("timestamp_ms"),
        pl.lit(None).cast(pl.Datetime).alias("test"),
    )
    return


if __name__ == "__main__":
    app.run()
