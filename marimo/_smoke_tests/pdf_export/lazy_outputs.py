import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # `mo.lazy` export smoke test
    """)


@app.cell
def _(mo):
    mo.md("""
    ## 1) Eager value (non-callable)
    """)


@app.cell
def _(mo):
    mo.lazy("EAGER_VALUE_MARKER")


@app.cell
def _(mo):
    mo.md("""
    ## 2) Sync function
    """)


@app.cell
def _(mo):
    def make_sync():
        return "SYNC_FUNCTION_MARKER"

    mo.lazy(make_sync)


@app.cell
def _(mo):
    mo.md("""
    ## 3) Async function
    """)


@app.cell
def _(mo):
    async def make_async():
        return "ASYNC_FUNCTION_MARKER"

    mo.lazy(make_async)


if __name__ == "__main__":
    app.run()
