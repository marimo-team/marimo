import marimo

__generated_with = "0.0.6"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    mo.md("This is an e2e test to capture bugs encountered that we don't want to show up again.")
    return mo,


@app.cell
def __(mo):
    bug_1 = mo.ui.number(1, 10)
    mo.md("bug 1")
    return bug_1,

@app.cell
def __(bug_1):
    bug_1
    return


@app.cell
def __(bug_1):
    bug_1.value
    return


if __name__ == "__main__":
    app.run()
