# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(
        """
        # Incrementing functions
        Bug from [#704](https://github.com/marimo-team/marimo/discussions/704)
        """
    )
    return


@app.cell
def __(mo):
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
