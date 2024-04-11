# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.64"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo, time):
    while True:
        time.sleep(1)
        mo.output.append(mo.md("Hello!"))
    return


@app.cell
def __():
    import time
    return time,


if __name__ == "__main__":
    app.run()
