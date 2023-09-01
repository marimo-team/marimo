# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.2"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import math
    return math,


@app.cell
def __():
    import random
    return random,


@app.cell
def __():
    import time
    return time,


@app.cell
def __(mo):
    state, set_state = mo.state(0)
    return set_state, state


@app.cell
def __(set_state, state):
    # No self-loops: shouldn't be a cycle
    set_state(state.value)
    return


@app.cell
def __(state):
    state.value
    return


@app.cell
def __(mo, set_state):
    _on_click = lambda _: set_state(lambda v: v + 1)
    button = mo.ui.button(
        value=0, on_click=_on_click
    )
    button
    return button,


@app.cell
def __(mo):
    # tie two number components together
    angle, set_angle = mo.state(0)
    return angle, set_angle


@app.cell
def __(angle, mo, set_angle):
    degrees = mo.ui.number(
        0, 360, step=1, value=angle.value, on_change=set_angle, label="degrees"
    )
    return degrees,


@app.cell
def __(angle, math, mo, set_angle):
    radians = mo.ui.number(
        0,
        2*math.pi,
        step=0.01,
        value=angle.value * math.pi / 180,
        on_change=lambda v: set_angle(v * 180 / math.pi),
        label="radians"
    )
    return radians,


@app.cell
def __(degrees, radians):
    degrees, radians
    return


if __name__ == "__main__":
    app.run()
