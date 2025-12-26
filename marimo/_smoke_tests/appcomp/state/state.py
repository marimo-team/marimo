# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    get_state, set_state = mo.state(False)
    return get_state, set_state


@app.cell
def _(mo, set_state):
    b = mo.ui.button(on_change=lambda x: set_state(True))
    b
    return


@app.cell
def _(get_state):
    "button was clicked" if get_state() else "button was not clicked"
    return


if __name__ == "__main__":
    app.run()
