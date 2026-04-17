# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Tooltips

    ## Markdown tooltips (via data-tooltip attribute)

    <span data-tooltip="Hello world!">Hover me (plain text)</span>
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Button with tooltip in label

    The label contains a `data-tooltip` span — handled by `wrapTooltipTargets` inside the Shadow DOM.
    """)
    return


@app.cell
def _(mo):
    mo.ui.button(label="<span data-tooltip='I said dont press'>Don't press</span>")
    return


@app.cell
def _(mo):
    mo.md("""
    ## mo.ui.button with tooltip arg

    Tooltip is handled by the plugin (ButtonPlugin) inside the Shadow DOM.
    Should NOT produce a duplicate tooltip from `wrapTooltipTargets`.
    """)
    return


@app.cell
def _(mo):
    mo.ui.button(tooltip="Click me!", label="Button with tooltip")
    return


@app.cell
def _(mo):
    mo.md("""
    ## mo.ui.run_button with tooltip arg
    """)
    return


@app.cell
def _(mo):
    mo.ui.run_button(tooltip="Run clicky")
    return


@app.cell
def _(mo):
    mo.md("""
    ## mo.ui.button with keyboard shortcut (no explicit tooltip)

    Should show the shortcut as a tooltip.
    """)
    return


@app.cell
def _(mo):
    mo.ui.button(label="Save", keyboard_shortcut="Ctrl-S")
    return


@app.cell
def _(mo):
    mo.md("""
    ## mo.ui.button with both tooltip and keyboard shortcut

    Explicit tooltip takes precedence over the shortcut tooltip.
    """)
    return


@app.cell
def _(mo):
    mo.ui.button(
        label="Submit",
        tooltip="Submit the form",
        keyboard_shortcut="Ctrl-Enter",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## mo.ui.form with submit/clear button tooltips
    """)
    return


@app.cell
def _(mo):
    mo.ui.text(label="Name").form(
        submit_button_label="Go",
        submit_button_tooltip="Submit the form",
        show_clear_button=True,
        clear_button_label="Reset",
        clear_button_tooltip="Clear all fields",
    )
    return


if __name__ == "__main__":
    app.run()
