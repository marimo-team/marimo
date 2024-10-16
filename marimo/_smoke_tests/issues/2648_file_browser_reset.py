import marimo

__generated_with = "0.9.9"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    source = mo.ui.text()
    source
    return (source,)


@app.cell
def __(mo, source):
    mo.ui.file_browser(initial_path=source.value)
    return


@app.cell
def __(mo):
    from vega_datasets import data

    df = data.cars()
    columns = df.columns.tolist()
    slider = mo.ui.slider(0, len(columns), label="frozen columns")
    slider
    return columns, data, df, slider


@app.cell
def __(columns, df, mo, slider):
    frozen = columns[: slider.value]
    mo.ui.table(df, freeze_columns_left=frozen)
    return (frozen,)


if __name__ == "__main__":
    app.run()
