import marimo

__generated_with = "0.13.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""When viewing this notebook in run mode, the hourglass loading indicator should be stickied to the top left even when scrolling down.""")
    return


@app.cell
def _(mo):
    mo.md("hello world" * 10000)
    return


@app.cell
def _():
    import time

    time.sleep(100)
    return


if __name__ == "__main__":
    app.run()
