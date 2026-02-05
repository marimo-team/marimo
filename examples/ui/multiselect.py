import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    multiselect = mo.ui.multiselect(options=["Apples", "Oranges", "Pears"])
    multiselect
    return (multiselect,)


@app.cell
def _(multiselect):
    multiselect.value
    return


if __name__ == "__main__":
    app.run()
