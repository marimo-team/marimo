# Copyright 2026 Marimo. All rights reserved.
import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    explained = mo.ui.button(
        value=0,
        on_click=lambda value: value + 1,
        label="Run analysis",
        disabled=True,
        tooltip="Select a dataset first",
        keyboard_shortcut="Ctrl-L",
        full_width=True,
    )
    unexplained = mo.ui.button(label="Unavailable", disabled=True)
    enabled = mo.ui.button(
        value=0,
        on_click=lambda value: value + 1,
        label="Enabled action",
        tooltip="Run the selected analysis",
    )
    mo.vstack([explained, unexplained, enabled])
    return enabled, explained


@app.cell
def _(enabled, explained, mo):
    mo.md(f"Disabled count: {explained.value}; enabled count: {enabled.value}")
    return


if __name__ == "__main__":
    app.run()
