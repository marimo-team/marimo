# Copyright 2026 Marimo. All rights reserved.
# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    sliders = [
        mo.ui.slider(
            start=0,
            stop=stop,
            step=step,
            value=0,
            label=label,
            show_value=True,
            full_width=True,
            include_input=include_input,
        )
        for label, stop, step, include_input in [
            ("Repeating step", 60, 1 / 30, False),
            ("Editable value", 60, 1 / 30, True),
        ]
    ]
    mo.vstack(sliders)
    return (sliders,)


if __name__ == "__main__":
    app.run()
