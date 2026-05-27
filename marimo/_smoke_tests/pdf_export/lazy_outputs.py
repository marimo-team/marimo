import marimo

__generated_with = "0.23.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("# `mo.lazy` export smoke test")
    return


@app.cell
def _(mo):
    mo.md("## 1) Eager value (non-callable)")
    return


@app.cell
def _(mo):
    mo.lazy("EAGER_VALUE_MARKER")
    return


@app.cell
def _(mo):
    mo.md("## 2) Sync function")
    return


@app.cell
def _(mo):
    def make_sync():
        return "SYNC_FUNCTION_MARKER"

    mo.lazy(make_sync)
    return


@app.cell
def _(mo):
    mo.md("## 3) Async function")
    return


@app.cell
def _(mo):
    async def make_async():
        return "ASYNC_FUNCTION_MARKER"

    mo.lazy(make_async)
    return


if __name__ == "__main__":
    app.run()
