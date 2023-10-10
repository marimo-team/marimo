# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.21"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(mo, time):
    for _ in mo.loading.progress_bar(
        range(10), title="Loading", subtitle="Please wait"
    ):
        time.sleep(0.1)
    return


@app.cell
def __(mo, time):
    mo.loading.spinner(title="Loading...")
    time.sleep(1)
    mo.ui.table([1, 2, 3])
    return


if __name__ == "__main__":
    app.run()
