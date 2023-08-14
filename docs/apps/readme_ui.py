import marimo

__generated_with = "0.0.13"
app = marimo.App()


@app.cell
def __(mo):
    x = mo.ui.slider(1, 9)
    x
    return x,


@app.cell
def __(math, mo, x):
    mo.md(f"$e^{x.value} = {math.exp(x.value):0.3f}$")
    return


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    form = mo.ui.slider(1, 9).form()
    form
    return form,


@app.cell
def __(form, mo):
    mo.md(f"The last submitted value is **{form.value}**")
    return


@app.cell
def __():
    import math
    return math,


if __name__ == "__main__":
    app.run()
