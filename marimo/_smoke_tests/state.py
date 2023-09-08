# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.4"
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
    get_state, set_state = mo.state(0)
    return get_state, set_state


@app.cell
def __(get_state, set_state):
    # No self-loops: shouldn't be a cycle
    set_state(get_state())
    return


@app.cell
def __(get_state):
    get_state()
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
    get_angle, set_angle = mo.state(0)
    return get_angle, set_angle


@app.cell
def __(get_angle, mo, set_angle):
    degrees = mo.ui.number(
        0, 360, step=1, value=get_angle(), on_change=set_angle, label="degrees"
    )
    return degrees,


@app.cell
def __(get_angle, math, mo, set_angle):
    radians = mo.ui.number(
        0,
        2*math.pi,
        step=0.01,
        value=get_angle() * math.pi / 180,
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
