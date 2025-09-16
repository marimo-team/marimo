import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    print("__file__", __file__)
    return


@app.cell
def _(mo):
    print("mo.notebook_dir()", mo.notebook_dir())
    return


if __name__ == "__main__":
    app.run()
