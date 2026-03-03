import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import asyncio

    return asyncio, mo


@app.cell
def _(mo):
    rerun = mo.ui.button(label="Rerun")
    rerun
    return (rerun,)


@app.cell
async def _(asyncio, mo, rerun):
    rerun
    for _ in mo.status.progress_bar(
        range(10),
        title="Loading",
        subtitle="Please wait",
        show_eta=True,
        show_rate=True,
    ):
        await asyncio.sleep(0.5)
    return


@app.cell
def _(mo):
    rerun_slow = mo.ui.button(label="Rerun Slow")
    rerun_slow
    return (rerun_slow,)


@app.cell
async def _(asyncio, mo, rerun_slow):
    rerun_slow
    for _ in mo.status.progress_bar(
        range(2), title="Loading", subtitle="Please wait", show_eta=True, show_rate=True
    ):
        await asyncio.sleep(12)
    return


if __name__ == "__main__":
    app.run()
