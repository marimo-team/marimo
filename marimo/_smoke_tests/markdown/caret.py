import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""
    ## Superscript

    H^2^O

    E = mc^2^

    x^2^ + y^2^ = z^2^

    This is text^with\ superscript^ in the middle.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Insert (underline)

    ^^Insert me^^

    This is ^^important^^ text that should be underlined.

    Here is some ^^newly added content^^ in the document.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Combined with other formatting

    **Bold with ^^inserted^^ text**

    *Italic with ^superscript^ text*

    ~~Deleted text~~ and ^^inserted text^^

    CH~3~CH~2~OH with H^2^O
    """)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
