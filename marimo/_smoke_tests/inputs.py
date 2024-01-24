# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.77"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    disabled = mo.ui.switch(label="Disabled")
    mo.hstack([disabled])
    return disabled,


@app.cell
def __(disabled, mo):
    mo.vstack(
        [
            mo.ui.text(label="Your name", disabled=disabled.value),
            mo.ui.text(label="Your tagline", max_length=30, disabled=disabled.value),
            mo.ui.text_area(label="Your bio", max_length=180, disabled=disabled.value),
        ]
    )
    return


@app.cell
def __(mo):
    options = ["red", "green", "blue"]

    mo.vstack(
        [
            mo.ui.dropdown(options, label="Dropdown"),
            mo.ui.multiselect(options, label="Multi-select"),
        ]
    )
    return options,


@app.cell
def __(mo, options):
    mo.ui.radio(options, label="Radio buttons")
    return


@app.cell
def __(mo, options):
    mo.ui.radio(options, label="Radio buttons", inline=True)
    return


if __name__ == "__main__":
    app.run()
