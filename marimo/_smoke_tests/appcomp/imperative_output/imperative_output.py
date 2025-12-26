# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("# hello")
    return


@app.cell
def _(mo, time):
    for i in mo.status.progress_bar(range(5)):
        time.sleep(0.5)
        print(i)
    return


@app.cell
def _(mo):
    import time
    mo.output.replace(mo.md("# output"))
    time.sleep(0.5)
    mo.output.replace(mo.md("# replaced"))
    return (time,)


if __name__ == "__main__":
    app.run()
