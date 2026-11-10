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

    chapter = mo.ui.dropdown(
        {"Start": 0, "Middle": 0.5, "End": 1},
        value="Start",
        label="Chapter",
    )
    chapter
    return chapter, mo


@app.cell
def _(chapter, mo):
    sliders = [
        mo.ui.slider(
            start=0,
            stop=stop,
            step=step,
            value=chapter.value * stop,
            label=label,
            show_value=True,
            full_width=True,
            include_input=include_input,
        )
        for label, stop, step, include_input in [
            ("Repeating step", 60, 1 / 30, False),
            ("Small range", 1, 1 / 30, False),
            ("Decimal step", 60, 0.1, False),
            ("Binary step", 60, 0.25, False),
            ("Tiny step", 1e-5, 1e-7, False),
            ("Editable value", 60, 1 / 30, True),
        ]
    ]
    mo.vstack(sliders)
    return (sliders,)


if __name__ == "__main__":
    app.run()
