# Copyright 2024 Marimo. All rights reserved.


import marimo

__generated_with = "0.4.7"
app = marimo.App()


@app.cell
async def __():
    import asyncio
    print("hello")
    await asyncio.sleep(1)
    print("world")
    await asyncio.sleep(1)
    print("last one")
    return asyncio,


if __name__ == "__main__":
    app.run()
