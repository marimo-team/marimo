import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import asyncio
    import concurrent.futures

    def blocking():
        return "done"
    return asyncio, blocking, concurrent


@app.cell
async def _(asyncio, blocking, concurrent):
    loop = asyncio.get_running_loop()
    with concurrent.futures.ProcessPoolExecutor() as pool:
        res = await loop.run_in_executor(pool, blocking)
    return


if __name__ == "__main__":
    app.run()
