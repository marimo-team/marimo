# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.17.3"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""::lucide:alarm-clock::""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.hstack(
        [
            mo.md("Color"),
            mo.icon("lucide:leaf", size=20),
            mo.icon("lucide:leaf", size=20, color="blue"),
            mo.icon("lucide:leaf", size=20, color="tomato"),
            mo.icon("lucide:leaf", size=20, color="green"),
            mo.icon("lucide:leaf", size=20, color="navy"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.md("Flip"),
            mo.icon("lucide:leaf", size=20),
            mo.icon("lucide:leaf", size=20, flip="vertical"),
            mo.icon("lucide:leaf", size=20, flip="horizontal"),
            mo.icon("lucide:leaf", size=20, flip="vertical,horizontal"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.md("Rotate"),
            mo.icon("lucide:leaf", size=20),
            mo.icon("lucide:leaf", size=20, rotate="90deg"),
            mo.icon("lucide:leaf", size=20, rotate="180deg"),
            mo.icon("lucide:leaf", size=20, rotate="270deg"),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.md("In buttons"),
            mo.ui.button(
                label=f"{mo.icon('material-symbols:rocket-launch')} Launch"
            ),
            mo.ui.button(label=f"::material-symbols:rocket-launch:: Launch"),
            mo.ui.button(label=f"Clear ::material-symbols:close-rounded::"),
            # Left and right
            mo.ui.button(
                label=f"::material-symbols:download:: Download ::material-symbols:csv::"
            ),
        ],
        justify="start",
    )
    return


@app.cell
def _(mo):
    mo.md(f"""## {mo.icon('material-symbols:edit')} Icons in markdown""")
    return


@app.cell
def _(mo):
    mo.tabs(
        {
            f"{mo.icon('material-symbols:group')} Overview": mo.md("Tab 1"),
            f"{mo.icon('material-symbols:group-add')} Add": mo.md("Tab 2"),
            f"{mo.icon('material-symbols:group-remove')} Remove": mo.md("Tab 3"),
        }
    )
    return


if __name__ == "__main__":
    app.run()
