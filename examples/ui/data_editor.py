import marimo

__generated_with = "0.19.7"
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
def _(DATA_FILE, mo, os):
    import polars as pl

    if not os.path.exists(DATA_FILE):
        from vega_datasets import data

        data.cars().to_csv(DATA_FILE)

    editor = mo.ui.data_editor(pl.read_csv(DATA_FILE)).form(bordered=False)
    editor
    return (editor,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    The following cell writes the updated dataframe to disk when the submit button is clicked.
    """)
    return


@app.cell
def _(DATA_FILE, editor, mo):
    mo.stop(editor.value is None, mo.md("Submit your changes."))

    editor.value.write_csv(DATA_FILE)
    return


if __name__ == "__main__":
    app.run()
