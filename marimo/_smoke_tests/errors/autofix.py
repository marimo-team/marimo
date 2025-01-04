import marimo

__generated_with = "0.10.9"
app = marimo.App(width="medium")


@app.cell
def _():
    x = 1
    return (x,)


@app.cell
def _():
    x = 2
    x
    return (x,)


@app.cell
def _():
    x = 3
    return (x,)


@app.cell
def _(mo):
    mo.md()
    return


@app.cell
def _(alt):
    alt.Chart()
    return


if __name__ == "__main__":
    app.run()
