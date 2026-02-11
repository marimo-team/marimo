import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    file_browser = mo.ui.file_browser()
    file_browser
    return (file_browser,)


@app.cell
def _(file_browser):
    file_browser.value
    return


if __name__ == "__main__":
    app.run()
