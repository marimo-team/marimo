# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "geodatasets==2024.8.0",
#     "geopandas==1.1.1",
#     "mapclassify==2.10.0",
#     "marimo",
#     "matplotlib==3.10.3",
#     "pandas==2.3.1",
#     "polars==1.31.0",
# ]
# ///

import marimo

__generated_with = "0.14.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def _(mo, pd):
    # https://github.com/marimo-team/marimo/issues/5445
    df = pd.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
    )
    float64_cols = df.select_dtypes(include="float64").columns
    df[float64_cols] = df[float64_cols].astype("Float64")
    object_cols = df.select_dtypes(include=["object"]).columns
    df[object_cols] = df[object_cols].astype("string")
    df
    mo.ui.dataframe(df)
    return (df,)


@app.cell
def _(df):
    df.dtypes
    return


@app.cell
def _():
    import geopandas as gpd
    from geodatasets import get_path
    import polars as pl

    path_to_data = get_path("nybb")
    gdf = gpd.read_file(path_to_data)
    return gdf, pl


@app.cell
def _(gdf):
    # This is ugly
    gdf
    return


@app.cell
def _(gdf):
    # This interactive leaflet map does work like a charm
    gdf.explore()
    return


@app.cell
def _(gdf, mo):
    # https://github.com/marimo-team/marimo/issues/5447
    mo.ui.table(gdf)
    return


@app.cell
def _(gdf):
    type(gdf)
    return


@app.cell
def _(gdf, mo):
    # This should not fail
    # https://github.com/marimo-team/marimo/issues/5447
    mo.ui.dataframe(gdf)
    return


@app.cell
def _(gdf, mo, pl):
    pl_df = pl.DataFrame(gdf.assign(geometry=gdf.geometry.astype(str)))
    mo.ui.dataframe(pl_df)
    return


if __name__ == "__main__":
    app.run()
