# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.17.6"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    b = mo.ui.button(value=None, label="Bad button", on_click=lambda v: v + 1)
    b
    return (b,)


@app.cell
def _(b):
    b.value
    return


@app.cell
def _(mo):
    disabled_btn = mo.ui.button(
        value=0,
        label="<div data-tooltip='Why disabled'>Disabled button</div>",
        on_click=lambda v: v + 1,
        disabled=True,
    )
    disabled_btn
    return (disabled_btn,)


@app.cell
def _(disabled_btn, mo):
    mo.md(f"disabled value: {disabled_btn.value}")
    return


@app.cell
def _(mo):
    enabled_btn = mo.ui.button(
        value=0,
        label="<div data-tooltip='Enabled tooltip'>Enabled button</div>",
        on_click=lambda v: v + 1,
        disabled=False,
    )
    enabled_btn
    return (enabled_btn,)


@app.cell
def _(enabled_btn, mo):
    mo.md(f"enabled value: {enabled_btn.value}")
    return


if __name__ == "__main__":
    app.run()
