# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.accordion(
        {
            """**e)** Diria que o trabalho, a educação e a idade explicam muita da variação no sono? Que outros fatores poderiam afetar o tempo passado a dormir? Estarão esses fatores provavelmente correlacionados com o trabalho?""": """
        - Content
        """
        }
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
