# Copyright 2026 Marimo. All rights reserved.
import marimo

app = marimo.App(width="medium")


@app.cell
async def async_cell():
    import asyncio

    await asyncio.sleep(0)
    value = 42
    return (value,)


if __name__ == "__main__":
    app.run()
