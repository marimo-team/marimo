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
    b = mo.ui.number(cli_name="test")
    a = mo.ui.number(1, 10, 1, cli_name="number")
    c = mo.ui.number()
    mo.hstack([a, b, c])
    return a, b, c


@app.cell
def _(a, b, c):
    print(a.value, b.value, c.value)
    return


@app.cell
def _(mo):
    print(mo.ui._impl.input.parser.format_help())
    return


@app.cell
def _(mo):
    mo.ui._impl.input.parser.add_help
    return


if __name__ == "__main__":
    app.run()
