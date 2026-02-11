import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    slider = mo.ui.slider(start=1, stop=10)
    slider
    return (slider,)


@app.cell
def _(slider):
    slider.value
    return


if __name__ == "__main__":
    app.run()
