import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    t = mo.ui.date()
    n = mo.ui.slider(1, 10)
    return n, t


@app.cell
def _(mo, n, t):
    mo.hstack([t, n], justify="start")
    return


@app.cell
def _(mo, n, t):
    mo.vstack([t, n])
    return


@app.cell
def _(mo):
    mo.hstack(
        [
            mo.stat(value=1, bordered=True),
            mo.stat(value=2, bordered=True),
            mo.stat(value=3, bordered=True),
        ],
        widths="equal",
    )
    return


@app.cell
def _(mo):
    text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Name faucibus risus in feugiat pharetra. Praesent vel ex nibh. "
    q = mo.vstack([mo.md(text)] * 5)
    s = mo.vstack([mo.md(str(0.5))] * 5, align="end", justify="space-between")
    mo.hstack([q, s], widths=[5, 1])
    return


if __name__ == "__main__":
    app.run()
