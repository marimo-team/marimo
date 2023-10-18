import marimo

__generated_with = "0.1.30"
app = marimo.App(width="full")


@app.cell
def __(cars, mo):
    df = mo.ui.dataframe(cars)
    df
    return df,


@app.cell
def __(df, mo):
    mo.ui.table(df.value, selection=None)
    return


@app.cell
def __(df):
    df.value
    return


@app.cell
def __(df):
    df.value["Cylinders"]
    return


@app.cell
def __(df, mo):
    mo.hstack([df.value.to_dict("records"), df.value.to_dict()])
    return


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import pandas as pd
    import vega_datasets

    cars = vega_datasets.data.cars()
    return cars, pd, vega_datasets


if __name__ == "__main__":
    app.run()
