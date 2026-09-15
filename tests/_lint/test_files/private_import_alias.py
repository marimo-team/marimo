import marimo

__generated_with = "0.24.0"
app = marimo.App()

with app.setup:
    import os as _os


@app.cell
def _():
    # Repeated: same `os as _os` as the setup cell above
    import os as _os

    _os.getcwd()
    return


@app.cell
def _():
    # Negative case: only occurs once, should NOT be flagged
    import json as _json

    return


@app.cell
def _():
    from collections import OrderedDict as _OrderedDict

    return


@app.cell
def _():
    # Repeated: same `OrderedDict as _OrderedDict` as the cell above
    from collections import OrderedDict as _OrderedDict

    return


@app.cell
def _():
    # Negative case: plain import should NOT be flagged
    import sys

    return


@app.cell
def _():
    # Negative case: no alias, just a module named with a leading
    # underscore, should NOT be flagged
    import _thread

    return


@app.cell
def _():
    # Negative case: aliasing to a public name should NOT be flagged
    import numpy as np

    return


if __name__ == "__main__":
    app.run()
