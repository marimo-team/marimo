import marimo

__generated_with = "0.12.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import os
    return (os,)


@app.cell
def _():
    DATA_FILE = "data.csv"
    return (DATA_FILE,)


@app.cell
def _(DATA_FILE, os):
    if not os.path.exists(DATA_FILE):
        from vega_datasets import data

        data.cars().to_csv(DATA_FILE)


    import polars as pl

    df = pl.read_csv(DATA_FILE)
    return data, df, pl


@app.cell
def _(df, mo):
    editor = mo.ui.data_editor(df).form(bordered=False)
    editor
    return (editor,)


@app.cell
def _(mo):
    mo.md(
        "The following cell writes the updated dataframe to disk when the submit button is clicked."
    )
    return


@app.cell
def _(DATA_FILE, editor):
    editor.value.write_csv(DATA_FILE)
    return


if __name__ == "__main__":
    app.run()
