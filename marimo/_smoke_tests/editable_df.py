import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import pandas as pd
    import marimo as mo

    params = [
        "Weight",
        "Torque",
        "Width",
        "Height",
        "Efficiency",
        "Power",
        "Displacement",
    ]
    return mo, params, pd, pl


@app.cell
def _(params, pd, pl):
    row_oriented = [
        dict(Model=i, **{param: 0 for param in params}) for i in range(1, 5)
    ]
    column_oriented = {param: [0 for _ in range(1, 5)] for param in params}
    polars_df = pl.DataFrame(row_oriented)
    pandas_df = pd.DataFrame(row_oriented)
    return column_oriented, pandas_df, polars_df, row_oriented


@app.cell
def _(mo):
    mo.md(r"""## Editing different inputs (dicts, lists, polars, pandas)""")
    return


@app.cell(hide_code=True)
def _(column_oriented, mo, pandas_df, polars_df, row_oriented):
    df = mo.ui.dropdown(
        {
            "polars": polars_df,
            "pandas": pandas_df,
            "row": row_oriented,
            "column": column_oriented,
        },
        value="polars",
        label="Table",
    )
    df
    return (df,)


@app.cell
def _(df, mo):
    edited = mo.ui.data_editor(df.value)
    edited
    return (edited,)


@app.cell
def _(edited, mo):
    mo.vstack(
        [
            mo.ui.table(edited.value, selection=None),
            flatten_edits(edited._edits["edits"]),
        ]
    )
    return


@app.function
def flatten_edits(edits):
    return [
        f"{edit['rowIdx']}.{edit['columnId']} -> {edit['value']}"
        for edit in edits
    ]


@app.cell
def _(mo):
    mo.md(r"""## Editing different data types""")
    return


@app.cell
def _(pd):
    import datetime

    large_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."

    varying_data = {
        "strings": ["a", "b", "c", large_text],
        "numbers": [1, 2, 3, 4],
        "bools": [True, False, True, False],
        "timestamps": [pd.Timestamp("2021-01-01") for _ in range(4)],
        "dates": [datetime.date(2021, 1, 1) for _ in range(4)],
        "datetimes": [datetime.datetime(2021, 1, 1, 1, 1, 1) for _ in range(4)],
        "duration": [datetime.timedelta(days=2, seconds=13500) for _ in range(4)],
        "none": [None for _ in range(4)],
        "lists": [[1, 2], [3, 4], [5, 6], [7, 8]],
    }
    return (varying_data,)


@app.cell
def _(pl, varying_data):
    pl.DataFrame(varying_data).schema
    return


@app.cell
def _(mo, pl, varying_data):
    edited_df = mo.ui.data_editor(pl.DataFrame(varying_data))
    edited_df
    return (edited_df,)


@app.cell
def _(edited_df):
    edited_df.value
    return


if __name__ == "__main__":
    app.run()
