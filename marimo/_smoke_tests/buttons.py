# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    kinds = ["neutral", "success", "warn", "danger"]

    mo.vstack([mo.ui.button(label=kind, kind=kind) for kind in kinds])
    return (kinds,)


@app.cell
def _(kinds, mo):
    mo.vstack([mo.ui.button(label=kind, kind=kind, disabled=True) for kind in kinds])
    return


if __name__ == "__main__":
    app.run()
