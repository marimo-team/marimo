import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    dropdown = mo.ui.dropdown(["Option A", "Option B", "Option C"])
    dropdown
    return (dropdown,)


@app.cell
def _(dropdown):
    dropdown.value
    return


if __name__ == "__main__":
    app.run()
