# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.42"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(
        """
        First Header  | Second Header
        ------------- | -------------
        Content Cell  | Content Cell
        $f(x)$        | Content Cell
        """
    )
    return


if __name__ == "__main__":
    app.run()
