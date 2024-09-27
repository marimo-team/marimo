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

    # hover:bg-muted/50 data-[state=selected]:bg-muted
    memtable = ibis.memtable(
        {
            "rowid": range(3000),
            "a": [1, 2, 3] * 1000,
            "b": [4, 5, 6] * 1000,
            "c": [4, 5, 6] * 1000,
            "d": [4, 5, 6] * 1000,
            "e": [4, 5, 6] * 1000,
        }
    )

    table = mo.ui.table(memtable, page_size=5)
    return ibis, memtable, table


@app.cell
def __(table):
    table
    return


@app.cell
def __(mo, table):
    mo.ui.table(table.value)
    return


@app.cell
def __(table):
    table.value
    return


if __name__ == "__main__":
    app.run()
