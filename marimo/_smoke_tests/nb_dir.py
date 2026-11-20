import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    print("__file__", __file__)


@app.cell
def _(mo):
    print("mo.notebook_dir()", mo.notebook_dir())


if __name__ == "__main__":
    app.run()
