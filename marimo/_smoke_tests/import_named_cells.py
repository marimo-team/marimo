# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from named_cells import display_slider, display_element
    return display_element, display_slider


@app.cell
def _(mo):
    mo.md("""**A cell that creates and shows a slider**""")
    return


@app.cell
def _(display_slider):
    slider_output, slider_defs = display_slider.run()
    slider_output
    return (slider_defs,)


@app.cell
def _(mo):
    mo.md("""_Notice that set-ui-element value requests make it into the defs_""")
    return


@app.cell
def _(slider_defs):
    slider_defs
    return


@app.cell
def _(slider_defs):
    slider_defs["slider"].value
    return


@app.cell
def _(mo):
    mo.md("""**A cell that shows a parametrizable UI element**""")
    return


@app.cell
def _(display_element, mo):
    text = mo.ui.text(placeholder="custom input")
    _o, _ = display_element.run(element=text)
    _o
    return (text,)


@app.cell
def _(text):
    text.value
    return


if __name__ == "__main__":
    app.run()
