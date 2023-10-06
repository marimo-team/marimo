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
    progress = mo.loading.start(
        title="Loading", subtitle="Please wait...", total=10
    )

    for i in range(10):
        time.sleep(.1)
        progress.update()
    return i, progress


@app.cell
def __(mo, time):
    progress2 = mo.loading.start(title="Loading", subtitle="Please wait...")
    time.sleep(1)
    progress2.update(title="Loading", subtitle="Checking for updates...")
    time.sleep(1)
    progress2.update(title="Loading", subtitle="Compiling...")
    time.sleep(1)
    progress2.update(title="Loading", subtitle="Done!")
    time.sleep(1)
    progress2.clear()
    return progress2,


@app.cell
def __(mo):
    # just spin
    mo.hstack(
        [
            mo.loading.start(),
            mo.loading.start(title="Loading..."),
            mo.loading.start(subtitle="Loading..."),
        ],
        align="center",
    )
    return


@app.cell
def __(mo, time):
    mo.loading.spinner(title="Loading...")
    time.sleep(1)
    mo.ui.table([1, 2, 3])
    return


if __name__ == "__main__":
    app.run()
