import marimo

__generated_with = "0.1.19"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(mo, time):
    def loop_replace():
        for i in range(5):
            mo.output.replace(mo.md(f"Loading replace {i}/5"))
            time.sleep(.1) # This is long enough to see the replace

    def loop_append():
        for i in range(5):
            mo.output.append(mo.md(f"Loading {i}/5"))
            time.sleep(.01) # This should be shorter than the replace
    return loop_append, loop_replace


@app.cell
def __(loop_replace, mo):
    loop_replace()
    mo.md("Replaced!")
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Appended!"))
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Cleared!"))
    mo.output.clear()
    return


@app.cell
def __(loop_append, mo):
    loop_append()
    mo.output.append(mo.md("Cleared!"))
    mo.output.replace(None)
    return


if __name__ == "__main__":
    app.run()
