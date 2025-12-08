import marimo

__generated_with = "0.18.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import pandas as pd
    import numpy as np
    return mo, np, pd, pl


@app.cell
def _(mo, np, pl):
    polars_df = pl.DataFrame({"nans": [1.0, np.nan, np.inf, -np.inf, None]})
    mo.vstack([mo.plain(polars_df), polars_df])
    return


@app.cell
def _(np, pd, pl):
    pl.DataFrame(
        {"nans_not_strict": [1.0, np.nan, np.inf, -np.inf, None, pd.NA, pd.NaT]},
        strict=False,
    )
    return


@app.cell
def _(mo, np, pd):
    pandas_df_obj = pd.DataFrame(
        {"nans": [1, None, pd.NaT, np.nan, pd.NA, np.inf, -np.inf]}
    )
    mo.vstack([mo.plain(pandas_df_obj), pandas_df_obj])
    return


@app.cell
def _(pd):
    # Filtering NaNs work for float types
    pandas_nan_float = pd.DataFrame({"nans": [1, 2, 3, 4, float("nan")]})
    pandas_nan_float
    return


if __name__ == "__main__":
    app.run()
