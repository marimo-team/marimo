import marimo

__generated_with = "0.15.3"
app = marimo.App(width="medium")


@app.function
async def sleep(seconds):
    import asyncio

    tasks = [asyncio.create_task(asyncio.sleep(s, s)) for s in seconds]
    for future in asyncio.as_completed(tasks):
        yield await future


@app.cell
async def _() -> None:
    import marimo as mo

    async def test_progress_async() -> None:

        ait = sleep([0.3, 0.2, 0.1])
        result = [s async for s in mo.status.progress_bar(ait, total=3)]
        assert result == [0.1, 0.2, 0.3]

    await test_progress_async()
    return


@app.cell
def _() -> None:
    return


@app.cell
def _() -> None:
    return


if __name__ == "__main__":
    app.run()
