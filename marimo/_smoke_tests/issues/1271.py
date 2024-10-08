# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.7"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    with mo.status.spinner(remove_on_exit=False):
        pass
    return


@app.cell
def __(mo):
    counter_button = mo.ui.button(
        value=0, on_click=lambda value: value + 1, label="increment"
    )
    counter_button
    return counter_button,


@app.cell
def __(counter_button, mo):
    mo.vstack([
        counter_button.value,
        mo.status.spinner(remove_on_exit=False) if counter_button.value < 3 else mo.md("Done!"),
    ])
    return


if __name__ == "__main__":
    app.run()
