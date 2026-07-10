# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# [tool.marimo.runtime]
# auto_instantiate = false
# on_cell_change = "lazy"
# [tool.marimo.display]
# theme = "dark"
# cell_output = "below"
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    This is not auto-run because it has custom marimo configuration in the file header:

    ```toml
    [tool.marimo.runtime]
    auto_instantiate = false
    on_cell_change = "lazy"
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
