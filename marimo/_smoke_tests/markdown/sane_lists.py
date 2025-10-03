import marimo

__generated_with = "0.16.2"
app = marimo.App(width="columns")


@app.cell(column=0, hide_code=True)
def _(mo):
    mo.md(r"""## Random numbering""")
    return


@app.cell
def _(mo):
    mo.md(
        """
    2. hey
    2. hey
    2. hey
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
    1. hey
    1. hey
    1. hey
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    1. hey
    2. hey
    2. hey
    """
    )
    return


@app.cell(column=1, hide_code=True)
def _(mo):
    mo.md(r"""## List without breaks""")
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    Lists with new line break (GitHub supports this)
    - hey
    - hey
      - hey
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    Lists with new line break (GitHub supports this)
    1. one
    2. two
      - two two
    """
    )
    return


@app.cell(column=2, hide_code=True)
def _(mo):
    mo.md(r"""## List with 2 or 4 indentation""")
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    Lists with 2-space indents (GitHub supports this)

    - hey
      - hey
        - hey
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    Lists with 4-space indents (GitHub supports this)

    1. hey
        1. hey
        2. hey
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    1. Item 1
      1. Nested ordered item
        1. Deep nested ordered
    2. Item 2
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    - List
       - indent with 3 spaces
          - indent with 6 spaces
    """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
