import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    source = mo.ui.text()
    source
    return (source,)


@app.cell
def _(mo, source):
    mo.ui.file_browser(initial_path=source.value)
    return


@app.cell
def _(mo):
    from vega_datasets import data

    df = data.cars()
    columns = df.columns.tolist()
    slider = mo.ui.slider(0, len(columns), label="frozen columns")
    slider
    return columns, df, slider


@app.cell
def _(columns, df, mo, slider):
    frozen = columns[: slider.value]
    mo.ui.table(df, freeze_columns_left=frozen)
    return


if __name__ == "__main__":
    app.run()
