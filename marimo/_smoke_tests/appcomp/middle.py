import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from inner import app
    return app,


@app.cell
def __(mo):
    mo.md("# middle")
    return


@app.cell
async def __(app):
    await app.embed()
    return


if __name__ == "__main__":
    app.run()
