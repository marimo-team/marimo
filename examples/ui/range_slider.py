import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    range_slider = mo.ui.range_slider(start=1, stop=10)
    range_slider
    return (range_slider,)


@app.cell
def _(range_slider):
    range_slider.value
    return


if __name__ == "__main__":
    app.run()
