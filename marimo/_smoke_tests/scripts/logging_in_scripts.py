import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import time
    return mo, time


@app.cell
def _(mo, time):
    for i in mo.status.progress_bar(range(10)):
        print(f"Step {i}")
        time.sleep(1)
    return


if __name__ == "__main__":
    app.run()
