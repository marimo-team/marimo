import marimo

__generated_with = "0.0.5"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    mo.md("# Cell 1")
    return mo,


@app.cell
def __(mo):
    mo.md("# Cell 2")
    return


if __name__ == "__main__":
    app.run()
