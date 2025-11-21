# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.17.6"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    b = mo.ui.button(value=None, label="Bad button", on_click=lambda v: v + 1)
    b
    return (b,)


@app.cell
def _(b):
    b.value
    return


if __name__ == "__main__":
    app.run()
