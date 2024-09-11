# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    kinds = [
        # ---
        "info",
        "note",
        # ---
        "danger",
        "error",
        "caution",
        # ---
        "hint",
        # ---
        "important",
        # ---
        "tip",
        # ---
        "attention",
        "warning",
    ]


    def create(kind):
        return mo.md(
            rf"""

            !!! {kind} "{kind} admonition"
                This is an admonition for {kind}
            """
        )


    mo.vstack([create(kind) for kind in kinds])
    return create, kinds


@app.cell
def __(mo):
    mo.md("""# Misc""")
    return


@app.cell
def __(mo):
    mo.md(
        rf"""
        !!! important ""
            This is an admonition box without a title.
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        !!! tip ""
            Importa recordar as seguintes regras de diferenciação de matrizes:
        
            $$\frac{\partial\, u'v}{\partial\, v} = \frac{\partial\, v'u}{\partial\, v} = u$$
        
            sendo $u$ e $v$ dois vetores.
        
            $$\frac{\partial\, v'Av}{\partial\, v}=2Av=2v'A$$
        
            em que $A$ é uma matriz simétrica. No nosso caso, $A=X'X$ e $v=\hat{\boldsymbol{\beta}}$.import marimo as mo
        """
    )
    return


if __name__ == "__main__":
    app.run()
