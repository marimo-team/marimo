# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "python-gcode==0.1.0",
# ]
#
# [tool.uv.sources]
# python-gcode = { git = "https://github.com/fetlab/python_gcode", rev = "new" }
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def foo():
    import marimo as mo


@app.cell
def _():
    import python_gcode
    help(python_gcode)


if __name__ == "__main__":
    app.run()
