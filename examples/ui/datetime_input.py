import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    datetime = mo.ui.datetime(label="datetime")
    datetime
    return (datetime,)


@app.cell
def _(datetime):
    datetime.value
    return


if __name__ == "__main__":
    app.run()
