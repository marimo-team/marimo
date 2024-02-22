import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one():
    import numpy as np
    import asyncio
    return asyncio, np


@app.cell
async def two(asyncio):
    x = 0
    xx = 1
    await asyncio.sleep(1)
    return x, xx


@app.cell
def three(asyncio, x):
    async def _():
        await asyncio.sleep(x)
    return


if __name__ == "__main__":
    app.run()
