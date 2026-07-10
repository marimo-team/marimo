import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Use `mo.md` with an `f-string` to create markdown that depends on the value of Python objects.
    """)
    return


@app.cell
def _():
    name = "Alice"
    return (name,)


@app.cell
def _(mo, name):
    mo.md(
        f"""
        Hello, {name}!
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Embed marimo UI elements in markdown directly:
    """)
    return


@app.cell
def _(mo):
    text_input = mo.ui.text(placeholder="My name is ...", debounce=False)
    return (text_input,)


@app.cell
def _(mo, text_input):
    mo.md(
        f"""
        What's your name? {text_input}

        Hello, {text_input.value}!
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Wrap plots and data structures in `mo.as_html()` to hook into marimo's rich media viewer:
    """)
    return


@app.cell
def _(mo):
    mo.md(
        f"""
        Here's a list of numbers:

        {mo.as_html([1, 2, 3])}
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
