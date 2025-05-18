import marimo

__generated_with = "0.11.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    return mo, pl


@app.cell
def _(pl):
    data = pl.DataFrame([range(11), range(11)])
    data = data.to_dicts()
    return (data,)


@app.cell
def _(data, mo):
    t1 = mo.ui.table(data, selection="single")
    t1
    return (t1,)


@app.cell
def _(t1):
    t1.value
    return


@app.cell
def _(data, mo):
    t2 = mo.ui.table(data, selection="multi")
    t2
    return (t2,)


@app.cell
def _(t2):
    t2.value
    return


@app.cell
def _(data, mo):
    t3 = mo.ui.table(data, selection="single-cell")
    t3
    return (t3,)


@app.cell
def _(t3):
    t3.value
    return


@app.cell
def _(data, mo):
    t4 = mo.ui.table(data, selection="multi-cell")
    t4
    return (t4,)


@app.cell
def _(t4):
    t4.value
    return


if __name__ == "__main__":
    app.run()
