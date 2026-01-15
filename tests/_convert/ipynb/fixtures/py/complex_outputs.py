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
    # Testing Various Output Types

    This notebook tests various output scenarios.
    """)
    return


@app.cell
def _():
    """Cell with print statements."""
    print("Standard output")
    print("Multiple lines")
    return


@app.cell
def _(mo):
    """Cell with rich output."""
    data = {"x": [1, 2, 3], "y": [4, 5, 6]}
    mo.ui.table(data)
    return (data,)


@app.cell
def _(data):
    """Cell with calculations and implicit output."""
    result = sum(data["x"]) + sum(data["y"])
    result
    return


@app.cell
def _(mo):
    """Cell with multiple outputs."""
    mo.md("## Section 1")
    print("Debug info")
    value = 42
    value
    return


@app.cell
def error_cell():
    """This would cause an error if run."""
    # Note: This is valid Python, just demonstrates error handling
    import sys

    if hasattr(sys, "never_exists"):
        raise ValueError("This should not happen")
    success = True
    return


if __name__ == "__main__":
    app.run()
