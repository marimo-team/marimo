# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    toggle = mo.ui.checkbox(label="Trigger ancestor error")
    toggle
    return (toggle,)


@app.cell
def _(toggle):
    if toggle.value:
        raise ValueError("ancestor error")

    x = 1
    return (x,)


@app.cell(disabled=True)
def _(x):
    y = x + 1
    return (y,)


@app.cell
def _(y):
    z = y + 1
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
