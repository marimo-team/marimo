import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Buttons
    """)


@app.cell
def _(mo):
    full_width = mo.ui.checkbox(label="Full width")
    full_width
    return (full_width,)


@app.cell
def _(full_width, mo):
    items = [
        mo.ui.button(label="button", full_width=full_width.value),
        mo.ui.text(label="button"),
    ]
    return (items,)


@app.cell
def _(items: list, mo):
    mo.vstack(items)


@app.cell
def _(items: list, mo):
    mo.hstack(items)


@app.cell
def _(items: list, mo):
    different_height_items = [
        *items,
        mo.ui.text_area(label="button"),
    ]
    return (different_height_items,)


@app.cell
def _(different_height_items: list, mo):
    mo.vstack(different_height_items)


@app.cell
def _(different_height_items: list, mo):
    mo.hstack(different_height_items)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Sliders
    """)


@app.cell(hide_code=True)
def _(full_width):
    full_width


@app.cell
def _(full_width, mo):
    range_slider = mo.ui.range_slider(
        start=1, stop=10, step=2, value=[2, 6], full_width=full_width.value
    )
    range_slider
    return (range_slider,)


@app.cell
def _(mo, range_slider):
    mo.hstack([range_slider])


@app.cell
def _(mo, range_slider):
    mo.vstack([range_slider])


@app.cell
def _(full_width, mo):
    slider = mo.ui.slider(start=1, stop=10, step=2, full_width=full_width.value)
    slider
    return (slider,)


@app.cell
def _(mo, slider):
    mo.hstack([slider])


@app.cell
def _(mo, slider):
    mo.vstack([slider])


if __name__ == "__main__":
    app.run()
