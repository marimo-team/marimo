import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    from imperative_output import app
    return app,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    for i in mo.status.progress_bar(range(5)):
        ...
    return i,


@app.cell
async def __(app):
    await app.embed()
    return


@app.cell
def __(app, mo):
    mo.ui.tabs({"MY TAB": mo.lazy(app.embed), "OTHER TAB": "foo"})
    return


if __name__ == "__main__":
    app.run()
