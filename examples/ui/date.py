import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    date = mo.ui.date()
    date
    return (date,)


@app.cell
def _(date):
    date.value
    return


if __name__ == "__main__":
    app.run()
