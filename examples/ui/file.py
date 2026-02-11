import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    file = mo.ui.file()
    file
    return (file,)


@app.cell
def _(file):
    file.value
    return


if __name__ == "__main__":
    app.run()
