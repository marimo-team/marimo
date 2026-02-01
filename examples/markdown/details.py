import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Create expandable markdown blocks with `details`:
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// details | Hello, details!

    Some additional content.

    ///
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Style details using the "type" argument:
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// details | Info details
        type: info

    Some additional content.
    ///
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// details | Warning details
        type: warn

    This highlights something to watch out for
    ///
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// details | Danger details
        type: danger

    This indicates a critical warning or dangerous situation
    ///
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// details | Success details
        type: success

    This indicates a successful outcome or positive note
    ///
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
