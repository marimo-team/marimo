import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    rerun = mo.ui.button(label="Rerun")
    rerun
    return (rerun,)


@app.cell
async def _(mo, rerun):
    import asyncio

    rerun
    with mo.status.spinner(title="Loading...") as _spinner:
        await asyncio.sleep(1)
        _spinner.update("Almost done")
        await asyncio.sleep(1)
        _spinner.update("Done")
    return


if __name__ == "__main__":
    app.run()
