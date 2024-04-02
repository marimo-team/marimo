# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.2.8"
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
            mo.ui.text(
                label="Your tagline", max_length=30, disabled=disabled.value
            ),
            mo.ui.text_area(
                label="Your bio", max_length=180, disabled=disabled.value
            ),
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


@app.cell
def __(mo):
    slider = mo.ui.slider(0, 10, label="Horizontal slider")
    vslider = mo.ui.slider(0, 10, orientation="vertical", label="Vertical slider")
    mo.hstack([slider, vslider])
    return slider, vslider


@app.cell
def __(mo):
    _slider = mo.ui.slider(0, 100, label="Horizontal slider", show_value=True)
    _vslider = mo.ui.slider(
        0, 100, orientation="vertical", label="Vertical slider", show_value=True
    )
    mo.hstack([_slider, _vslider])
    return


if __name__ == "__main__":
    app.run()
