import marimo

__generated_with = "0.18.4"
app = marimo.App(width="columns")


@app.cell(column=0)
def _():
    import marimo as mo
    import polars as pl
    import pandas as pd
    import ibis as ib

    from vega_datasets import data
    return data, ib, mo, pd, pl


@app.cell
def _(data, ib, pd, pl):
    cars = data.cars()
    df_pandas = pd.DataFrame(cars)
    df_polars = pl.DataFrame(cars)
    df_ibis = ib.memtable(cars)
    return df_ibis, df_pandas, df_polars


@app.cell(column=1)
def _(df_pandas, mo):
    mo.ui.dataframe(df_pandas)
    return


@app.cell
def _(df_polars, mo):
    mo.ui.dataframe(df_polars)
    return


@app.cell
def _(df_ibis, mo):
    mo.ui.dataframe(df_ibis)
    return


@app.cell(column=2)
def _(df_pandas):
    df_pandas_next = df_pandas
    df_pandas_next = df_pandas_next.pivot_table(
        index=["Year"],
        columns=["Origin"],
        values=["Acceleration"],
        aggfunc="mean",
        sort=False,
        fill_value=None,
    ).sort_index(axis=0)
    df_pandas_next.columns = [
        f"{'_'.join(map(str, col)).strip()}_mean"
        if isinstance(col, tuple)
        else f"{col}_mean"
        for col in df_pandas_next.columns
    ]
    df_pandas_next = df_pandas_next.reset_index()
    df_pandas_next
    return


@app.cell
def _(df_polars):
    df_polars_next = df_polars
    df_polars_next = df_polars_next.pivot(
        on=["Origin"],
        index=["Year"],
        values=["Acceleration"],
        aggregate_function="mean",
    ).sort(["Year"])
    replacements = str.maketrans({"{": "", "}": "", '"': "", ",": "_"})
    df_polars_next = df_polars_next.rename(
        lambda col: f"Acceleration_{col.translate(replacements)}_mean"
        if col not in ["Year"]
        else col
    )
    df_polars_next
    return


@app.cell
def _(df_ibis):
    df_ibis_next = df_ibis
    df_ibis_next = df_ibis_next.pivot_wider(
        names_from=["Origin"],
        id_cols=["Year"],
        values_from=["Acceleration"],
        names_prefix="Acceleration",
        values_agg="mean",
    )
    df_ibis_next = df_ibis_next.rename(
        **{
            f"{col}_mean": col
            for col in df_ibis_next.columns
            if col not in ["Year"]
        }
    )
    df_ibis_next.to_polars()
    return


if __name__ == "__main__":
    app.run()
