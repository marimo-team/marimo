import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    button = mo.ui.button(
        value=0, on_click=lambda value: value + 1, label="increment", kind="warn"
    )
    button
    return (button,)


@app.cell
def _(button):
    button.value
    return


if __name__ == "__main__":
    app.run()
