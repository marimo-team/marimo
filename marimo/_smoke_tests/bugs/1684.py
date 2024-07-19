# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.5"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(
        r"""
        $$
        \begin{align*}
        x &= 1 && \tag{Taylor} \\
        x &= 1123123123123123 && \tag{Taylor's rule} \\
        \end{align*}
        $$
        """
    )
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
