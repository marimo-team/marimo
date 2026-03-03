# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.0.0"
app = marimo.App(width="medium", auto_download=["html"])


@app.cell
def _():
    x = 1
    return (x,)


@app.cell
def _(x):
    print(x)
    return


if __name__ == "__main__":
    app.run()
