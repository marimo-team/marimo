import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return


@app.function
async def wait_for(seconds):
    import asyncio
    print(f"Waiting for {seconds} seconds ...")
    await asyncio.sleep(seconds)
    print("Done!")


@app.cell
async def _():
    await wait_for(1)
    return


if __name__ == "__main__":
    app.run()
