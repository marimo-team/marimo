import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import sys
    import time
    return mo, sys, time


@app.cell
def _(mo, sys, time):
    for i in mo.status.progress_bar(range(10)):
        if i % 2 == 0:
            print(f"Step {i}", file=sys.stderr)
        else:
            print(f"Step {i}")
        time.sleep(1)
    return


if __name__ == "__main__":
    app.run()
