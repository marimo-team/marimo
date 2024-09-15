# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "marimo",
#     "polars",
# ]
# ///
import marimo

__generated_with = "0.6.23"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __(data):
    import polars as pl
    polars_df = pl.from_pandas(data.cars())
    return pl, polars_df


@app.cell
def __(mo, polars_df):
    mo.ui.slider.from_series(polars_df["Cylinders"])
    return


@app.cell
def __(mo, polars_df):
    mo.ui.number.from_series(polars_df["Cylinders"])
    return


@app.cell
def __(mo, polars_df):
    mo.ui.radio.from_series(polars_df["Origin"])
    return


@app.cell
def __(mo, polars_df):
    mo.ui.dropdown.from_series(polars_df["Origin"])
    return


@app.cell
def __(mo, polars_df):
    mo.ui.multiselect.from_series(polars_df["Origin"])
    return


@app.cell
def __(mo, polars_df):
    mo.ui.date.from_series(polars_df["Year"])
    return


@app.cell
def __(data, mo):
    pandas_df = data.cars()
    [
        mo.ui.slider.from_series(pandas_df["Cylinders"]),
        mo.ui.number.from_series(pandas_df["Cylinders"]),
        mo.ui.radio.from_series(pandas_df["Origin"]),
        mo.ui.dropdown.from_series(pandas_df["Origin"]),
        mo.ui.multiselect.from_series(pandas_df["Origin"]),
        mo.ui.date.from_series(pandas_df["Year"])
    ]
    return pandas_df,


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
