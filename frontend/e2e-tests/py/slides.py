# /// script
# [tool.marimo.runtime]
# auto_instantiate = true
# ///

import marimo

__generated_with = "0.19.4"
app = marimo.App(layout_file="layouts/slides.slides.json")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Slides!
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We all love slides don't we 🎀
    """)
    return


if __name__ == "__main__":
    app.run()
