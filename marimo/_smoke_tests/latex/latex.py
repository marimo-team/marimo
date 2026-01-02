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
        # Incrementing functions
        Bug from [#704](https://github.com/marimo-team/marimo/discussions/704)
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        \begin{align}
            B' &=-\nabla \times E,\\
            E' &=\nabla \times B - 4\pi j\\
            e^{\pi i} + 1 = 0
        \end{align}
        """
    )
    return


if __name__ == "__main__":
    app.run()
