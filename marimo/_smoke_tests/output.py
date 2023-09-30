# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.19"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import time
    return time,


@app.cell
def __(mo, time):
    def loop_replace():
        for i in range(5):
            mo.output.replace(mo.md(f"Loading {i}/5"))
            time.sleep(.1)

    def loop_append():
        for i in range(5):
            mo.output.append(mo.md(f"Loading {i}/5"))
            time.sleep(.1)
    return loop_append, loop_replace


@app.cell
def __(mo):
    mo.md("### Replace")
    return


@app.cell
def __(loop_replace, mo):
    loop_replace()
    mo.md("Done!")
    return


@app.cell
def __(loop_replace, mo):
    loop_replace()
    mo.output.replace(mo.md(f"Done"))
    return


@app.cell
def __(mo):
    mo.md("### Append")
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.md("Done!")
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Done!"))
    return


@app.cell
def __(mo):
    mo.md("### Clear")
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Done!"))
    mo.output.clear()
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Done!"))
    mo.output.replace(None)
    return


@app.cell
def __(mo):
    mo.md("### Sleep (stale)")
    return


@app.cell
def __(time):
    time.sleep(2)
    "hello"
    return


if __name__ == "__main__":
    app.run()
