# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def __(mo):
    mo.md("""# 🤖 Lists/Dicts""")
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


@app.cell(hide_code=True)
def __(mo):
    mo.md("""# 🐼 Pandas""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.dataframe""")
    return


@app.cell
def __(cars, mo):
    dataframe = mo.ui.dataframe(cars)
    dataframe
    return dataframe,


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.table""")
    return


@app.cell
def __(dataframe, mo):
    mo.ui.table(dataframe.value, selection=None)
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## .value""")
    return


@app.cell
def __(dataframe):
    dataframe.value
    return


@app.cell
def __(dataframe):
    dataframe.value["Cylinders"]
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.data_explorer""")
    return


@app.cell
def __(mo, pl_dataframe):
    mo.ui.data_explorer(pl_dataframe)
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""# 🐻‍❄️ Polars""")
    return


@app.cell
def __(mo):
    mo.md("""## mo.ui.dataframe""")
    return


@app.cell
def __(mo, pl_dataframe):
    pl_dataframe_prime = mo.ui.dataframe(pl_dataframe)
    pl_dataframe_prime
    return pl_dataframe_prime,


@app.cell
def __(pl_dataframe_prime):
    pl_dataframe_prime.value
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.table""")
    return


@app.cell
def __(cars, mo, pl):
    pl_dataframe = pl.DataFrame(cars)
    mo.ui.table(pl_dataframe, selection=None)
    return pl_dataframe,


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.data_explorer""")
    return


@app.cell
def __(mo, pl_dataframe):
    mo.ui.data_explorer(pl_dataframe)
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""# 🏹 Arrow""")
    return


@app.cell
def __(cars, mo, pa):
    arrow_table = pa.Table.from_pandas(cars)
    mo.accordion({"Details": mo.plain_text(arrow_table)})
    return arrow_table,


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## mo.ui.table""")
    return


@app.cell
def __(arrow_table, mo):
    arrow_table_el = mo.ui.table(arrow_table)
    arrow_table_el
    return arrow_table_el,


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## .value""")
    return


@app.cell
def __(arrow_table_el):
    arrow_table_el.value
    return


@app.cell
def __(arrow_table, mo):
    mo.ui.data_explorer(arrow_table)
    return


@app.cell
def __(mo):
    mo.md(
        rf"""
        # 💽 Dataframe protocol
        > See the [API](https://data-apis.org/dataframe-protocol/latest/API.html)
        """
    )
    return


@app.cell
def __():
    import dask.dataframe as dd

    dask_df = dd.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
    )
    dask_df
    return dask_df, dd


@app.cell
def __():
    import ibis

    ibis.options.interactive = True

    ibis_data = ibis.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv",
        table_name="penguins",
    )
    ibis_data
    return ibis, ibis_data


@app.cell
def __(mo):
    mo.md(rf"## mo.ui.table")
    return


@app.cell
def __(ibis_data, mo):
    ibis_penguins = mo.ui.table(ibis_data)
    ibis_penguins
    return ibis_penguins,


@app.cell
def __(ibis_penguins):
    ibis_penguins.value
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(rf"## mo.ui.data_explorer")
    return


@app.cell
def __(ibis_data, mo):
    mo.ui.data_explorer(ibis_data)
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import vega_datasets
    import altair as alt

    cars = vega_datasets.data.cars()
    return alt, cars, mo, pa, pd, pl, vega_datasets


if __name__ == "__main__":
    app.run()
