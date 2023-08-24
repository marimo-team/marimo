import marimo

__generated_with = "0.1.2"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import random
    return random,


@app.cell
def __(mo):
    get_state, set_state = mo.state(0)
    return get_state, set_state


@app.cell
def __(set_state):
    set_state(10)
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


if __name__ == "__main__":
    app.run()
