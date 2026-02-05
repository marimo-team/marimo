import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    dictionary = mo.ui.dictionary({"name": mo.ui.text(), "age": mo.ui.slider(1, 100)})
    dictionary
    return (dictionary,)


@app.cell
def _(dictionary):
    dictionary.value
    return


if __name__ == "__main__":
    app.run()
