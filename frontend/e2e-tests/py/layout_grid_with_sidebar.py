# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.18.0"
app = marimo.App(layout_file="layouts/layout_grid_with_sidebar.grid.json")


@app.cell
def _(mo):
    mo.md("""
    # Grid with Sidebar
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Main Content Area
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### More content here
    """)
    return


@app.cell
def _(mo):
    mo.sidebar(
        [
            mo.md("# Sidebar Title"),
            mo.md("This sidebar should be visible in run mode"),
            mo.nav_menu(
                {
                    "#section1": "Section 1",
                    "#section2": "Section 2",
                    "#section3": "Section 3",
                },
                orientation="vertical",
            ),
        ]
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
