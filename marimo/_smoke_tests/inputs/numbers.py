import marimo

__generated_with = "0.8.20"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    mo.ui.number()
    return


@app.cell
def __(mo):
    mo.ui.number(-10, 10)
    return


@app.cell
def __(mo):
    # Above max safe int
    BAD_INT = 999999999999999990
    v = mo.ui.number(
        value=BAD_INT, start=BAD_INT - 5, stop=BAD_INT + 5, full_width=True
    )
    v
    return BAD_INT, v


@app.cell
def __(v):
    v.value
    return


if __name__ == "__main__":
    app.run()
