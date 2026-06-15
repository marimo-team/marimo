import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Slider smoke tests
    """)
    return


@app.cell
def _(mo):
    # --- Basic interval sliders ---
    basic = mo.ui.slider(1, 10)
    with_step = mo.ui.slider(1, 10, step=2, value=5, show_value=True)
    float_slider = mo.ui.slider(0.0, 1.0, step=0.1, value=0.5, show_value=True)
    negative = mo.ui.slider(-10, 10, value=0, show_value=True)
    with_input = mo.ui.slider(0, 100, value=42, include_input=True, show_value=True)
    debounced = mo.ui.slider(0, 10, value=5, debounce=True, show_value=True)
    disabled = mo.ui.slider(0, 10, value=3, disabled=True, show_value=True)
    vertical = mo.ui.slider(
        0, 10, value=5, orientation="vertical", show_value=True, label="Vertical"
    )
    full_width = mo.ui.slider(0, 10, value=5, full_width=True, label="Full width")
    labeled = mo.ui.slider(1, 5, value=2, label="**Markdown** label", show_value=True)
    return (
        basic,
        debounced,
        disabled,
        float_slider,
        full_width,
        labeled,
        negative,
        vertical,
        with_input,
        with_step,
    )


@app.cell
def _(basic, float_slider, mo, negative, with_input, with_step):
    mo.vstack(
        [
            mo.md("## Basic interval sliders"),
            mo.hstack([basic, mo.md("`start`/`stop` only (default value = start)")]),
            mo.hstack([with_step, mo.md("Integer range with `step=2`")]),
            mo.hstack([float_slider, mo.md("Float range with `step=0.1`")]),
            mo.hstack([negative, mo.md("Negative to positive range")]),
            mo.hstack([with_input, mo.md("`include_input=True` — type or use arrows")]),
        ],
        gap=1,
    )
    return


@app.cell
def _(debounced, disabled, full_width, labeled, mo, vertical):
    mo.vstack(
        [
            mo.md("## Options"),
            mo.hstack([debounced, mo.md("`debounce=True` — value commits on release")]),
            mo.hstack([disabled, mo.md("`disabled=True`")]),
            vertical,
            full_width,
            labeled,
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    # --- High-precision floats ---
    precision_milli = mo.ui.slider(
        label="1/1000 precision",
        start=0,
        stop=0.1,
        step=0.001,
        value=0.025,
        show_value=True,
        include_input=True,
    )
    precision_micro = mo.ui.slider(
        label="1/1,000,000 precision",
        start=0,
        stop=0.0001,
        step=0.000001,
        value=0.000025,
        show_value=True,
        include_input=True,
    )
    return precision_micro, precision_milli


@app.cell
def _(mo, precision_micro, precision_milli):
    mo.vstack(
        [
            mo.md("## Precision"),
            mo.md(
                "Values must display exactly — no rounding in the input or label."
            ),
            precision_milli,
            precision_micro,
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    # --- Custom steps (regression for #9850) ---
    steps_int = mo.ui.slider(
        steps=[1, 2, 3, 4],
        value=3,
        include_input=True,
        show_value=True,
        label="Integer steps",
    )
    steps_mixed = mo.ui.slider(
        steps=[1, 2, 3.5, 4],
        value=3.5,
        include_input=True,
        show_value=True,
        label="Mixed float steps",
    )
    steps_decimal = mo.ui.slider(
        steps=[0.1, 0.2, 0.3, 0.4],
        value=0.3,
        include_input=True,
        show_value=True,
        label="Decimal steps",
    )
    steps_negative = mo.ui.slider(
        steps=[-4, -3, -2, -1],
        value=-2,
        include_input=True,
        show_value=True,
        label="Negative steps",
    )
    return steps_decimal, steps_int, steps_mixed, steps_negative


@app.cell
def _(mo, steps_decimal, steps_int, steps_mixed, steps_negative):
    mo.vstack(
        [
            mo.md("## Custom `steps`"),
            mo.md(
                """
                With `include_input=True`, the text field must show the **actual**
                step value (not the index). Arrow keys and typing should move to
                valid steps only.
                """
            ),
            steps_int,
            steps_mixed,
            steps_decimal,
            steps_negative,
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    import numpy as np

    steps_numpy = mo.ui.slider(
        steps=np.logspace(0, 2, 5),
        show_value=True,
        include_input=True,
        label="NumPy logspace steps",
    )
    return (steps_numpy,)


@app.cell
def _(mo, steps_numpy):
    mo.vstack(
        [
            mo.md("## NumPy `steps`"),
            steps_numpy,
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    # --- Range sliders ---
    range_basic = mo.ui.range_slider(1, 10)
    range_with_value = mo.ui.range_slider(1, 10, step=2, value=[2, 6], show_value=True)
    range_steps = mo.ui.range_slider(
        steps=[1, 3, 6, 10, 17, 20],
        value=[3, 17],
        show_value=True,
        label="Range with custom steps",
    )
    return range_basic, range_steps, range_with_value


@app.cell
def _(mo, range_basic, range_steps, range_with_value):
    mo.vstack(
        [
            mo.md("## Range sliders"),
            range_basic,
            range_with_value,
            range_steps,
        ],
        gap=1,
    )
    return


@app.cell
def test_invalid_slider_raises(mo):
    import pytest

    with pytest.raises(ValueError, match="Invalid bounds"):
        mo.ui.slider(10, 1)

    with pytest.raises(ValueError, match="out of bounds"):
        mo.ui.slider(1, 10, value=11)

    with pytest.raises(ValueError, match="Invalid arguments"):
        mo.ui.slider(start=1, stop=10, steps=[1, 2, 3])
    return


if __name__ == "__main__":
    app.run()
