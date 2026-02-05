import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    switch = mo.ui.switch()
    switch
    return (switch,)


@app.cell
def _(switch):
    switch.value
    return


if __name__ == "__main__":
    app.run()
