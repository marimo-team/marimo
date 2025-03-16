import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.raw_cli_args()
    return (mo,)


@app.cell
def _(mo):
    b = mo.ui.number(key="number")
    a = mo.ui.slider(1, 10, 1, key="slider")
    c = mo.ui.range_slider(0, 100, 4, key="range_slider")
    mo.hstack([a, b, c])
    return a, b, c


@app.cell
def _(a, b, c):
    print(a.value, b.value, c.value)
    return


@app.cell
def _(mo):
    mo.md("""how to collect all ui's help messages for `python test.py --help`?""")
    return


@app.cell
def _(a, b, c, mo):
    data = f"{a.value=}, {b.value=}, {c.value=}"
    mo.download(data.encode(), key="download_str", filename="data_str.txt")
    return (data,)


@app.cell
def _(mo):
    func = lambda: b"callable data"
    mo.download(func, key="download_callable", filename="data_callable.txt")
    return (func,)


if __name__ == "__main__":
    app.run()
