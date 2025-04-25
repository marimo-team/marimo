import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def wait_for():
    async def wait_for(seconds):
        import asyncio
        print(f"Waiting for {seconds} seconds ...")
        await asyncio.sleep(seconds)
        print("Done!")
    return (wait_for,)


@app.cell
async def _(wait_for):
    await wait_for(1)
    return


if __name__ == "__main__":
    app.run()
