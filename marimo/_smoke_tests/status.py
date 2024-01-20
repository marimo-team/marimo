# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.63"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(mo, time):
    for _ in mo.status.progress_bar(
        range(10), title="Loading", subtitle="Please wait"
    ):
        time.sleep(0.1)
    return


@app.cell
def __(mo, time):
    for _ in mo.status.progress_bar(
        range(10), title="Loading", subtitle="Please wait", show_eta=True, show_rate=True
    ):
        time.sleep(0.5)
    return


@app.cell
def __(mo, time):
    with mo.status.spinner(title="Loading...", remove_on_exit=True) as _spinner:
        time.sleep(1)
        _spinner.update("Almost done")
        time.sleep(1)
    return


@app.cell
def __(mo, time):
    with mo.status.spinner(title="Loading...", remove_on_exit=True) as _spinner:
        time.sleep(1)
        _spinner.update("Almost done")
        time.sleep(1)
    mo.ui.table([1, 2, 3])
    return


if __name__ == "__main__":
    app.run()
