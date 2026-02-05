import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    element = mo.md("{start} → {end}").batch(
        start=mo.ui.date(label="Start"), end=mo.ui.date(label="End")
    )
    element
    return (element,)


@app.cell
def _(element):
    element.value
    return


if __name__ == "__main__":
    app.run()
