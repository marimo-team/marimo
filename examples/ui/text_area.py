import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    text_area = mo.ui.text_area(placeholder="type some text ...")
    text_area
    return (text_area,)


@app.cell
def _(text_area):
    text_area.value
    return


if __name__ == "__main__":
    app.run()
