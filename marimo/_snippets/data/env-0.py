# Copyright 2025 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Load .env""")
    return


@app.cell
def _():
    import dotenv

    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
    return (dotenv,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
