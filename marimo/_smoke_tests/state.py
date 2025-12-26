# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import math
    return (math,)


@app.cell
def _():
    import random
    return


@app.cell
def _():
    import time
    return


@app.cell
def _(mo):
    get_state, set_state = mo.state(0)
    return get_state, set_state


@app.cell
def _(get_state, set_state):
    # No self-loops: shouldn't be a cycle
    set_state(get_state())
    return


@app.cell
def _(get_state):
    get_state()
    return


@app.cell
def _(mo, set_state):
    _on_click = lambda _: set_state(lambda v: v + 1)
    button = mo.ui.button(
        value=0, on_click=_on_click
    )
    button
    return


@app.cell
def _(mo):
    # tie two number components together
    get_angle, set_angle = mo.state(0)
    return get_angle, set_angle


@app.cell
def _(get_angle, mo, set_angle):
    degrees = mo.ui.number(
        0, 360, step=1, value=get_angle(), on_change=set_angle, label="degrees"
    )
    return (degrees,)


@app.cell
def _(get_angle, math, mo, set_angle):
    radians = mo.ui.number(
        0,
        2*math.pi,
        step=0.01,
        value=get_angle() * math.pi / 180,
        on_change=lambda v: set_angle(v * 180 / math.pi),
        label="radians"
    )
    return (radians,)


@app.cell
def _(degrees, radians):
    degrees, radians
    return


if __name__ == "__main__":
    app.run()
