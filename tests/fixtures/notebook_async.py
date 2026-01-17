import marimo

app = marimo.App()


@app.cell
async def __():
    import asyncio
    await asyncio.sleep(0.1)
    return (asyncio,)


if __name__ == "__main__":
    app.run()
