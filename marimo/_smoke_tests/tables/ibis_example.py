import marimo

__generated_with = "0.8.15"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    import ibis

    table = ibis.memtable({"a": [1, 2, 3] * 1000, "b": [4, 5, 6] * 1000})

    mo.ui.table(table)
    return ibis, table


if __name__ == "__main__":
    app.run()
