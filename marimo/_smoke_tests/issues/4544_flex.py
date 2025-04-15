

import marimo

__generated_with = "0.12.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


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
def _(items, mo):
    mo.vstack(items)
    return


@app.cell
def _(items, mo):
    mo.hstack(items)
    return


@app.cell
def _(items, mo):
    different_height_items = [
        *items,
        mo.ui.text_area(label="button"),
    ]
    return (different_height_items,)


@app.cell
def _(different_height_items, mo):
    mo.vstack(different_height_items)
    return


@app.cell
def _(different_height_items, mo):
    mo.hstack(different_height_items)
    return


if __name__ == "__main__":
    app.run()
