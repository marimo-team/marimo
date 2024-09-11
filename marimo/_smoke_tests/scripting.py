# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.14"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("""hello""")
    return


@app.cell
def __(mo):
    mo.Html("<script>console.log(document.querySelectorAll('p')[0].textContent)</script>")
    return


if __name__ == "__main__":
    app.run()
