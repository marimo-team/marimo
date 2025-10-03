"""Example to test formatting issues."""

import marimo as mo  # intentional to test import aliasing

statement = "not in a cell, so unexpected"

# no generate guard
app = mo.App()

statement = "not in a cell, so unexpected"


@app.cell
def _():
    pass


# no run guard
