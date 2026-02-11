import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    button = mo.ui.run_button()
    button
    return (button,)


@app.cell
def _(button, mo):
    mo.stop(not button.value, "Click the button to continue")

    mo.md("# :tada:")
    return


if __name__ == "__main__":
    app.run()
