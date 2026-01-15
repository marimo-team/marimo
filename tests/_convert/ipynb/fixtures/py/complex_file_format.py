# /// script
# description = "Complex file format with setup cell"
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pandas>=2.1.0",
#     "numpy>=2.1.0",
# ]
# ///

import marimo

__generated_with = "0.19.2"
app = marimo.App(width="medium", auto_download=["html"], sql_output="native")

with app.setup:
    # Complex file format with setup cell
    import marimo as mo


@app.cell(hide_code=True)
def _():
    mo.md("""
    # Documentation

    This cell has **hidden code** and uses markdown.

    - Feature 1
    - Feature 2
    """)
    return


@app.cell
def imports():
    """Named cell with imports."""
    import pandas as pd
    import numpy as np
    return np, pd


@app.cell(disabled=True)
def disabled_cell():
    """This cell is disabled."""
    x = 42
    should_not_run = True
    return


@app.cell
def data_loading(np, pd):
    """Named cell for data loading."""
    df = pd.DataFrame({"a": np.array([1, 2, 3]), "b": np.array([4, 5, 6])})
    return (df,)


@app.cell
def analysis(df):
    """Named cell with analysis and markdown output."""
    result = df["a"].sum()
    mo.md(f"The sum is **{result}**")
    return


@app.cell
def _():
    """Unnamed cell."""
    internal_var = 100
    return


@app.function
def add(x, y):
    """Pure function."""
    return x + y


@app.function(hide_code=True)
def remove(x, y):
    """Hidden function."""
    return x - y


@app.class_definition
class MyClass:
    """Pure class."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def add(self):
        return self.x + self.y


@app.class_definition(hide_code=True)
class MyHiddenClass:
    """Hidden class."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def add(self):
        return self.x + self.y


if __name__ == "__main__":
    app.run()
