# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.11"
app = marimo.App()


@app.cell
def __(mo):
    b = mo.ui.run_button()
    b
    return b,


@app.cell
def __(mo):
    s = mo.ui.slider(1, 10)
    s
    return s,


@app.cell
def __(b, mo, s):
    mo.stop(not b.value, "Click `run` to submit the slider's value")

    s.value
    return


@app.cell
def __(b, mo):
    mo.stop(not b.value)

    import random
    random.randint(0, 1000)
    return random,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
