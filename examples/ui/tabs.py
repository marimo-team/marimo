import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    tabs = mo.ui.tabs({
        "Bob says": mo.md("Hello, Alice! 👋"),
        "Alice says": mo.md("Hello, Bob! 👋")
    })
    tabs
    return (tabs,)


@app.cell
def _(tabs):
    tabs.value
    return


if __name__ == "__main__":
    app.run()
