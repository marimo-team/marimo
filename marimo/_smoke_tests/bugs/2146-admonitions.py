import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("""
        Importa recordar as seguintes regras de diferenciação de matrizes:

        $$\frac{\partial\, u'v}{\partial\, v} = \frac{\partial\, v'u}{\partial\, v} = u$$

        sendo $u$ e $v$ dois vetores.

        $$\frac{\partial\, v'Av}{\partial\, v}=2Av=2v'A$$

        em que $A$ é uma matriz simétrica. No nosso caso, $A=X'X$ e $v=\hat{\boldsymbol{\beta}}$.
    """).callout()
    return


@app.cell
def __(mo):
    mo.md(
        """
        !!! tip ""
            Importa recordar as seguintes regras de diferenciação de matrizes:

            $$\frac{\partial\, u'v}{\partial\, v} = \frac{\partial\, v'u}{\partial\, v} = u$$

            sendo $u$ e $v$ dois vetores.

            $$\frac{\partial\, v'Av}{\partial\, v}=2Av=2v'A$$

            em que $A$ é uma matriz simétrica. No nosso caso, $A=X'X$ e $v=\hat{\boldsymbol{\beta}}$.
        """
    )
    return


@app.cell
def __(mo):
    mo.accordion(
        {
            "Tip": mo.md("""
        Importa recordar as seguintes regras de diferenciação de matrizes:

        $$\frac{\partial\, u'v}{\partial\, v} = \frac{\partial\, v'u}{\partial\, v} = u$$

        sendo $u$ e $v$ dois vetores.

        $$\frac{\partial\, v'Av}{\partial\, v}=2Av=2v'A$$

        em que $A$ é uma matriz simétrica. No nosso caso, $A=X'X$ e $v=\hat{\boldsymbol{\beta}}$.
    """)
        }
    )
    return


if __name__ == "__main__":
    app.run()
