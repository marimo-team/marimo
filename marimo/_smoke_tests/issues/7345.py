import marimo

__generated_with = "0.18.4"
app = marimo.App(width="columns")


@app.cell(column=0)
def _():
    import marimo as mo
    import narwhals as nw
    import polars as pl
    import pandas as pd

    # import ibis
    from vega_datasets import data
    return data, mo, pd, pl


@app.cell
def _(data, pd, pl):
    cars = data.cars()
    df_pandas = pd.DataFrame(cars)
    df_polars = pl.DataFrame(cars)
    return df_pandas, df_polars


@app.cell
def _():
    return


@app.cell(column=1)
def _(df_pandas, mo):
    mo.ui.dataframe(df_pandas)
    return


@app.cell
def _(df_polars, mo):
    mo.ui.dataframe(df_polars)
    return


@app.cell
def _():
    return


@app.cell(column=2)
def _(df_pandas):
    df_pandas_next = df_pandas
    df_pandas_next = df_pandas_next.pivot_table(index=["Year"], columns=["Origin"], values=["Acceleration"], aggfunc="mean", sort=False, fill_value=None).sort_index(axis=0)
    df_pandas_next.columns = [f"{'_'.join(map(str, col)).strip()}_mean" if isinstance(col, tuple) else f"{col}_mean" for col in df_pandas_next.columns]
    df_pandas_next = df_pandas_next.reset_index()
    df_pandas_next = df_pandas_next[["Year", "Acceleration_Europe_mean", "Acceleration_Japan_mean"]]
    df_pandas_next
    return


@app.cell
def _(df_polars):
    df_polars_next = df_polars
    df_polars_next = df_polars_next.pivot(on=["Origin"], index=["Year"], values=["Acceleration"], aggregate_function="median").sort(["Year"])
    replacements = str.maketrans({"{": "", "}": "", '"': "", ",": "_"})
    df_polars_next = df_polars_next.rename(lambda col: f'Acceleration_{col.translate(replacements)}_median' if col not in ["Year"] else col)
    df_polars_next = df_polars_next.select(["Year", "Acceleration_Europe_median", "Acceleration_Japan_median"])
    df_polars_next
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
