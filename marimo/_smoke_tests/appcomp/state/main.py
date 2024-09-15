# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    from state import app
    return app,


@app.cell
async def __(app):
    (await app.embed()).output
    return


if __name__ == "__main__":
    app.run()
