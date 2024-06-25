import marimo

__generated_with = "0.6.22"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    d = mo.ui.dropdown(["first", "second"], value="first")
    return d,


@app.cell
def __(d):
    d
    return


@app.cell
def __(d):
    "value is " + d.value
    return


if __name__ == "__main__":
    app.run()
