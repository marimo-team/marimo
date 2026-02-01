import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    checkbox = mo.ui.checkbox(label="check me")
    checkbox
    return (checkbox,)


@app.cell
def _(checkbox):
    checkbox.value
    return


if __name__ == "__main__":
    app.run()
