import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    items = [
        mo.md("# one"),
        mo.md("# two"),
        mo.md("## three"),
        mo.md("## four"),
    ]
    return (items,)


@app.cell
def _(items: list, mo):
    mo.hstack(items)
    return


@app.cell
def _(items: list, mo):
    mo.vstack(items)
    return


@app.cell
def _(items: list, mo):
    _items = [
        mo.md("a" * 200),
        mo.md("b" * 180),
        mo.md("c" * 160),
    ]
    mo.vstack(
        [
            mo.hstack(items),
            mo.md("---"),
            *_items,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
