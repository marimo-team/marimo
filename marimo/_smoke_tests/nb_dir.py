import marimo

__generated_with = "0.8.22"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(__file__):
    print("__file__", __file__)
    return


@app.cell
def __(mo):
    print("mo.notebook_dir()", mo.notebook_dir())
    return


if __name__ == "__main__":
    app.run()
