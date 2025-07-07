# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///
import marimo

__generated_with = "0.13.15"
app = marimo.App(layout_file="layouts/layout_grid.grid.json")


@app.cell
def _(mo):
    mo.md("""# Grid Layout""")
    return


@app.cell
def _(mo, search):
    mo.md(f"""Searching {search.value}""")
    return


@app.cell
def _(mo):
    search = mo.ui.text(label="Search")
    search
    return (search,)


@app.cell
def _(mo):
    mo.md("""text 1""")
    return


@app.cell
def _(mo):
    mo.md("""text 2""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
