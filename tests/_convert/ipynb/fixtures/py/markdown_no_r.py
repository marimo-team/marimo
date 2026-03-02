import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # No r-prefix

    This markdown uses triple quotes without r-prefix.
    """)
    return


if __name__ == "__main__":
    app.run()
