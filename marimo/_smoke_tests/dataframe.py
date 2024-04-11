# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.3.10"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md("# 🤖 Lists/Dicts")
    return


@app.cell
def __(mo):
    _data = [
        {"Name": "John", "Age": 30, "City": "New York"},
        {"Name": "Alice", "Age": 24, "City": "San Francisco"},
    ]
    as_list = mo.ui.table(_data)
    as_list
    return as_list,


@app.cell
def __(as_list):
    as_list.value
    return


@app.cell
def __(mo):
    _data = {
        "Name": ["John", "Alice"],
        "Age": [30, 24],
        "City": ["New York", "San Francisco"],
    }
    as_dict = mo.ui.table(_data)
    as_dict
    return as_dict,


@app.cell
def __(as_dict):
    as_dict.value
    return


@app.cell
def __(mo):
    _data = [1, 2, "hello", False]
    as_primitives = mo.ui.table(_data)
    as_primitives
    return as_primitives,


@app.cell
def __(as_primitives):
    as_primitives.value
    return


@app.cell
def __(mo):
    mo.md("# 🐼 Pandas")
    return


@app.cell
def __(mo):
    mo.md("## mo.ui.dataframe")
    return


@app.cell
def __(cars, mo):
    dataframe = mo.ui.dataframe(cars)
    dataframe
    return dataframe,


@app.cell
def __(mo):
    mo.md("## mo.ui.table")
    return


@app.cell
def __(dataframe, mo):
    mo.ui.table(dataframe.value, selection=None)
    return


@app.cell
def __(mo):
    mo.md("## .value")
    return


@app.cell
def __(dataframe):
    dataframe.value
    return


@app.cell
def __(dataframe):
    dataframe.value["Cylinders"]
    return


@app.cell
def __(mo):
    mo.md("## mo.ui.data_explorer")
    return


@app.cell
def __(mo, pl_dataframe):
    mo.ui.data_explorer(pl_dataframe)
    return


@app.cell
def __(mo):
    mo.md("# 🐻‍❄️ Polars")
    return


@app.cell
def __(mo):
    mo.md("## mo.ui.table")
    return


@app.cell
def __(cars, mo, pl):
    pl_dataframe = pl.DataFrame(cars)
    mo.ui.table(pl_dataframe, selection=None)
    return pl_dataframe,


@app.cell
def __(mo):
    mo.md("## mo.ui.data_explorer")
    return


@app.cell
def __(mo, pl_dataframe):
    mo.ui.data_explorer(pl_dataframe)
    return


@app.cell
def __(mo):
    mo.md("# 🏹 Arrow")
    return


@app.cell
def __(cars, mo, pa):
    arrow_table = pa.Table.from_pandas(cars)
    mo.accordion({"Details": mo.plain_text(arrow_table)})
    return arrow_table,


@app.cell
def __(mo):
    mo.md("## mo.ui.table")
    return


@app.cell
def __(arrow_table, mo):
    arrow_table_el = mo.ui.table(arrow_table)
    arrow_table_el
    return arrow_table_el,


@app.cell
def __(mo):
    mo.md("## .value")
    return


@app.cell
def __(arrow_table_el):
    arrow_table_el.value
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import vega_datasets

    cars = vega_datasets.data.cars()
    return cars, mo, pa, pd, pl, vega_datasets


if __name__ == "__main__":
    app.run()
