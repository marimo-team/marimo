import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Use colon syntax as a shortcut for **emojis** in your markdown.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    :rocket: :smile:
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
