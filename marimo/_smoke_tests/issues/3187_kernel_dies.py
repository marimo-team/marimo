import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import sys

    return (sys,)


@app.cell
def _(sys):
    sys.exit()


@app.cell
def _():
    import os

    return (os,)


@app.cell
def _(os):
    os._exit(1)


if __name__ == "__main__":
    app.run()
