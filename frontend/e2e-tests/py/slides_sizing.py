# Copyright 2026 Marimo. All rights reserved.
# /// script
# [tool.marimo.runtime]
# on_cell_change = "autorun"
# ///

import marimo

app = marimo.App(layout_file="layouts/slides.slides.json")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    parameter = mo.ui.slider(0, 10, value=5, label="Parameter")
    return (parameter,)


@app.cell
def _(mo, parameter):
    mo.vstack(
        [
            mo.md("# Resolution-independent slides"),
            mo.hstack(
                [
                    mo.md("""
                    ## Layout

                    This paragraph should keep the same line breaks when the
                    presentation moves between the editor, fullscreen, and a
                    projector with a different resolution.
                    """),
                    mo.md(r"""
                    ## Mathematics

                    $$f(x) = \sum_{j=1}^{n} \frac{x_j^2}{1 + x_j^2}$$
                    """),
                ],
                widths="equal",
                gap=2,
            ),
            parameter,
            mo.md(f"Parameter value: **{parameter.value}**"),
        ],
        gap=1,
    )
    return


if __name__ == "__main__":
    app.run()
