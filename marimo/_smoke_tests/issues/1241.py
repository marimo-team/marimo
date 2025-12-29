# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import leafmap.foliumap as leafmap

    m = leafmap.Map(center=(40, -100), zoom=4)
    return m, mo


@app.cell
def _(m):
    m  # Using our custom formatter
    return


@app.cell
def _(m, mo):
    mo.Html(m._repr_html_())  # Using the built-in ipython formatter
    return


if __name__ == "__main__":
    app.run()
