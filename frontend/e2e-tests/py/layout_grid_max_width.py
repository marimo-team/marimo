# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///
import marimo

__generated_with = "0.1.50"
app = marimo.App(layout_file="layouts/layout_grid_max_width.grid.json")


@app.cell
def __(mo):
    mo.md("# Grid Layout")
    return


@app.cell
def __(mo, search):
    mo.md(f"Searching {search.value}")
    return


@app.cell
def __(mo):
    search = mo.ui.text(label="Search")
    search
    return search,


@app.cell
def __(mo):
    mo.md("text 1")
    return


@app.cell
def __(mo):
    mo.md("text 2")
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
