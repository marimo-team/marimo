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
    progress = mo.loading.start(title='Loading', subtitle='Please wait...', total=20)

    for i in range(20):
        progress.update()
        time.sleep(0.1)
    return i, progress


@app.cell
def __(mo, time):
    progress2 = mo.loading.start(title='Loading', subtitle='Please wait...')
    time.sleep(2)
    progress2.update(title='Loading', subtitle='Checking for updates...')
    time.sleep(2)
    progress2.update(title='Loading', subtitle='Compiling...')
    time.sleep(2)
    progress2.update(title='Loading', subtitle='Done!')
    time.sleep(1)
    progress2.clear()
    return progress2,


@app.cell
def __(mo):
    # just spin
    mo.loading.start()
    return


if __name__ == "__main__":
    app.run()
