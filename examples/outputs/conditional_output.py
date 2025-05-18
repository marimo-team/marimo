import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    checkbox = mo.ui.checkbox()
    checkbox
    return (checkbox,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""Use inline if expressions to conditionally show a value""")
    return


@app.cell
def _(checkbox):
    "Checkbox is checked" if checkbox.value else "Checkbox is not checked"
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        The next cell does **not** show anything, since an if statement does not
        have a value:
        """
    )
    return


@app.cell
def _(checkbox, mo):
    if checkbox.value:
        mo.md("Checkbox is checked")
    else:
        mo.md("Checkbox is not checked")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""A value of `None` produces the empty output:""")
    return


@app.cell
def _(checkbox):
    checkbox
    return


@app.cell
def _(checkbox, mo):
    _output = None
    if checkbox.value:
        _output = mo.md("Checkbox is checked.")
    _output
    return


if __name__ == "__main__":
    app.run()
