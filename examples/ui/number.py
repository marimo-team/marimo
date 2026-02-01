import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    number = mo.ui.number(start=1, stop=10)
    number
    return (number,)


@app.cell
def _(number):
    number.value
    return


if __name__ == "__main__":
    app.run()
