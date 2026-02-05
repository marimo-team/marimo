import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    radio = mo.ui.radio(["A", "B", "C"])
    radio
    return (radio,)


@app.cell
def _(radio):
    radio.value
    return


if __name__ == "__main__":
    app.run()
