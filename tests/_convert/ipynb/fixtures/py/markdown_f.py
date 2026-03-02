import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(f"""
    # With f-prefix

    This markdown uses f-prefix but has no interpolation.
    """)
    return


if __name__ == "__main__":
    app.run()
