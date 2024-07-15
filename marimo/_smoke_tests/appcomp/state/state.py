# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    get_state, set_state = mo.state(False)
    return get_state, set_state


@app.cell
def __(mo, set_state):
    b = mo.ui.button(on_change=lambda x: set_state(True))
    b
    return b,


@app.cell
def __(get_state):
    "button was clicked" if get_state() else "button was not clicked"
    return


if __name__ == "__main__":
    app.run()
