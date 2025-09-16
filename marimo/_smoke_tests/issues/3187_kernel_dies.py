import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import sys
    return (sys,)


@app.cell
def _(sys):
    sys.exit()
    return


@app.cell
def _():
    import os
    return (os,)


@app.cell
def _(os):
    os._exit(1)
    return


if __name__ == "__main__":
    app.run()
