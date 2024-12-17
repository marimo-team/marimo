import marimo

__generated_with = "0.9.27"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def __(pd):
    pd.DataFrame([1, 2, 3])
    return


@app.cell
def __(pd):
    data = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])
    data
    return (data,)


@app.cell
def __(data, mo):
    mo.ui.table(data)
    return


if __name__ == "__main__":
    app.run()
