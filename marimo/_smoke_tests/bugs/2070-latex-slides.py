# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.8.0"
app = marimo.App(
    width="medium",
    layout_file="layouts/2070-latex-slides.slides.json",
)


@app.cell
def __():
    import marimo as mo

    mo.md("""
      ## Como detetar?

      - **Não existem testes estatísticos**
      - Alguns **indícios**
          - Coeficiente de correlação elevando entre pares de variáveis explicativas
          - A regressão de uma variável explicativas nas restantes produz um $R^2$ elevado
          - Acrescentar ou retirar observações provoca alterações significativa nos resultados
      - **Critério de diagnóstico:** VIF (*Variance Inflation Factor*)

      $$VIF \\equiv \frac{1}{(1-R^2_j)} > 10,\\quad j=1,\\dots,k$$

      em que $R^2_j$ é o $R^2$ da regressão da variável explicativa $j$ nas outras variáveis
    """)
    return mo,


@app.cell
def __(mo):
    mo.md("""# 2""")
    return


@app.cell
def __():
    return


@app.cell
def __(mo):
    mo.md("""# 3""")
    return


if __name__ == "__main__":
    app.run()
