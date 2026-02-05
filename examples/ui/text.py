import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    text = mo.ui.text()
    text
    return (text,)


@app.cell
def _(text):
    text.value
    return


if __name__ == "__main__":
    app.run()
