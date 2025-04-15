import marimo


app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo,):
    rerun = mo.ui.button(label="Rerun")
    rerun
    return (rerun,)

@app.cell
async def _(mo, rerun):
    import asyncio
    rerun
    for _ in mo.status.progress_bar(
        range(10),
        title="Loading",
        subtitle="Please wait",
        show_eta=True,
        show_rate=True
    ):
        await asyncio.sleep(0.5)
    return


if __name__ == "__main__":
    app.run()

