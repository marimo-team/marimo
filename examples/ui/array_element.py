import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    array = mo.ui.array([mo.ui.text(), mo.ui.slider(1, 10), mo.ui.date()])
    array
    return (array,)


@app.cell
def _(array):
    array.value
    return


if __name__ == "__main__":
    app.run()
