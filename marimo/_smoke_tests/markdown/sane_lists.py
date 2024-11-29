import marimo

__generated_with = "0.9.27"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(
        """
        2. hey
        2. hey
        2. hey
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
        1. hey
        1. hey
        1. hey
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        1. hey
        2. hey
        2. hey
        """
    )
    return


@app.cell
def __():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
