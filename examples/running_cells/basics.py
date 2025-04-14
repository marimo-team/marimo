import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        marimo knows how your cells are related, and can automatically update
        outputs like a spreadsheet. This eliminates hidden state and hidden bugs, accelerates data exploration, and makes it possible for marimo to run your notebooks as scripts and web apps.

        (For expensive notebooks, you can [turn this
        behavior off] via the notebook footer(https://docs.marimo.io/guides/expensive_notebooks/).)

        Try updating the values of variables below and see what happens! You can also try deleting a cell.
        """
    )
    return


@app.cell
def _():
    x = 0
    return (x,)


@app.cell
def _():
    y = 1
    return (y,)


@app.cell
def _(x):
    x
    return


if __name__ == "__main__":
    app.run()
