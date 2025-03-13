# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair==5.5.0",
#     "marimo",
#     "numpy==2.2.3",
#     "openai==1.66.2",
#     "pandas==2.2.3",
#     "polars==1.24.0",
#     "vegafusion==2.0.2",
#     "vl-convert-python==1.7.0",
# ]
# ///

import marimo

__generated_with = "0.11.18"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(alt, flights):
    _chart = (
        alt.Chart(flights)
        .mark_line(point={"filled": False, "fill": "white"})
        .encode(
            x=alt.X("date", type="temporal"),
            y=alt.Y("count()", type="quantitative"),
        )
        .properties(width="container")
    )
    _chart
    return


@app.cell
def _(mo):
    mo.md(r"""# Histograms with vegafusion""")
    return


@app.cell
def _():
    import polars as pl
    import altair as alt
    import vegafusion as vf

    # Requires vl-convert-python as well

    alt.data_transformers.enable("vegafusion")

    # Comment out to disable duckdb connection
    # vf.runtime.set_connection("duckdb")

    flights = pl.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_1m.parquet"
    )
    return alt, flights, pl, vf


@app.cell
def _(alt, flights):
    delay_hist = (
        alt.Chart(flights)
        .mark_bar()
        .encode(alt.X("delay", bin=alt.Bin(maxbins=30)), alt.Y("count()"))
    )
    delay_hist
    return (delay_hist,)


@app.cell
def _(flights, mo):
    mo.ui.table(flights[0:100], show_column_summaries=True)
    return


@app.cell
def _(alt, flights, mo):
    columns = flights.columns
    charts = []
    for col in columns:
        if flights[col].dtype.is_numeric() or flights[col].dtype.is_temporal():
            charts.append(
                alt.Chart(flights)
                .mark_bar()
                .encode(
                    alt.X(col, bin=alt.Bin(maxbins=15), axis=None),
                    alt.Y("count()", axis=None),
                    # Color nulls differently
                    color=alt.condition(
                        f"datum.bin_maxbins_15_{col}_range === null",
                        alt.value("#FDA4AF"),  # orange for nulls
                        alt.value("#027864"),  # mint for non-nulls
                    ),
                    tooltip=[col, "count()"],
                )
            )
        else:
            # aggregate
            charts.append(
                alt.Chart(flights)
                .mark_bar()
                .encode(
                    alt.X(col),
                    alt.Y("count()"),
                    # Color nulls differently
                    color=alt.condition(
                        f"datum.{col} === null",
                        alt.value("#FDA4AF"),  # orange for nulls
                        alt.value("#027864"),  # mint for non-nulls
                    ),
                    tooltip=[col, "count()"],
                )
            )
    mo.hstack(charts)
    return charts, col, columns


@app.cell
def _(delay_hist, mo):
    mo.md(
        f"Total buckets **{len(delay_hist.to_dict(format='vega')['data'][0]['values'])}**"
    )
    return


if __name__ == "__main__":
    app.run()
