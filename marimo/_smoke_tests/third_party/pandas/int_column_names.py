import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def _(pd):
    pd.DataFrame([1, 2, 3])
    return


@app.cell
def _(pd):
    data = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])
    data
    return (data,)


@app.cell
def _(data, mo):
    mo.ui.table(data)
    return


if __name__ == "__main__":
    app.run()
