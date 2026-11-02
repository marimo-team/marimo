import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    refresh = mo.ui.refresh(default_interval="3s")
    refresh
    return (refresh,)


@app.cell
def _(mo, refresh):
    refresh
    user = mo.app_meta().request.user
    [user]


@app.cell
def _(mo, refresh):
    refresh
    list(mo.app_meta().request.keys())


@app.cell
def _(mo, refresh):
    refresh
    mo.app_meta().request


if __name__ == "__main__":
    app.run()
