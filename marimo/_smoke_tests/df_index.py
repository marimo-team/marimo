import marimo

__generated_with = "0.14.12"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    return mo, np, pd


@app.cell
def _(np):
    data = np.random.randn(100, 2)
    columns = ["A", "B"]
    return columns, data


@app.cell
def _(columns, data, pd):
    df_no_index = pd.DataFrame(data, columns=columns)
    df_no_index
    return


@app.cell
def _(columns, data, pd):
    _dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    df_date_index = pd.DataFrame(data, index=_dates, columns=columns)
    df_date_index
    return (df_date_index,)


@app.cell
def _(columns, data, pd):
    _dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    df_date_index_with_name = pd.DataFrame(
        data, index=pd.DatetimeIndex(_dates, name="date"), columns=columns
    )
    df_date_index_with_name
    return


@app.cell
def _(columns, data, pd):
    _dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    df_category_index = pd.DataFrame(
        data, index=pd.CategoricalIndex(_dates), columns=columns
    )
    df_category_index
    return


@app.cell
def _(columns, data, pd):
    index = pd.MultiIndex.from_tuples(
        [(i, j) for i in range(5) for j in range(2)], names=["Level1", "Level2"]
    )
    df_multi_index = pd.DataFrame(data[:10], index=index, columns=columns)
    df_multi_index
    return


@app.cell
def _(df_date_index, mo):
    mo.ui.dataframe(df_date_index)
    return


if __name__ == "__main__":
    app.run()
