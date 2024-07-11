# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("# hello")
    return


@app.cell
def __(mo, time):
    for i in mo.status.progress_bar(range(5)):
        time.sleep(0.5)
        print(i)
    return i,


@app.cell
def __(mo):
    import time
    mo.output.replace(mo.md("# output"))
    time.sleep(0.5)
    mo.output.replace(mo.md("# replaced"))
    return time,


if __name__ == "__main__":
    app.run()
