import marimo

__generated_with = "0.13.6"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import time
    import asyncio


    async def background_task(name, seconds):
        """A simple task that prints messages at intervals."""
        print(f"Task {name} started")
        for i in range(seconds):
            print(f"Task {name}: working... ({i + 1}/{seconds})")
            await asyncio.sleep(1)
        print(f"Task {name} completed")
        return f"{name} result"
    return asyncio, background_task


@app.cell
def _(asyncio, background_task):
    # Run this cell for a new background task
    a = asyncio.create_task(background_task("A", 2))
    return


@app.cell
def _(asyncio, refresh):
    # This list should have at least one task (the kernel). When creating tasks above, they should be added and then removed.
    refresh
    list(asyncio.all_tasks())
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo

    refresh = mo.ui.refresh(options=["1s"], default_interval="1s")
    refresh
    return (refresh,)


if __name__ == "__main__":
    app.run()
