# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
#
# [tool.marimo.display]
# theme = "dark"
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
    mo.md(
        """
        This notebook sets `theme = "dark"` via inline `[tool.marimo.display]`
        metadata. It should render in dark mode even when opened from a
        directory listing (`marimo run marimo/_smoke_tests`). See #10056.
        """
    )
    return


if __name__ == "__main__":
    app.run()
