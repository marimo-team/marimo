import marimo

__generated_with = "0.15.2"
app = marimo.App()


@app.cell
def _():
    # This should trigger MB005 - syntax error with star import hint
    from math import *
    result = sin(pi / 2)
    return result,


@app.cell
def _():
    from pandas import *
    df = DataFrame({"a": [1, 2, 3]})
    return df,


@app.cell
def _():
    # This should NOT trigger syntax error - normal import
    import numpy as np
    arr = np.array([1, 2, 3])
    return arr,


@app.cell
def _():
    # This should NOT trigger syntax error - specific imports
    from typing import List, Dict
    data: List[Dict[str, int]] = [{"x": 1}, {"y": 2}]
    return data,


@app.cell
def _():
    # Another star import but
    # Pad out import statement
    # with
    # super
    # comments
    from os import *
    current_dir = getcwd()
    return current_dir,


if __name__ == "__main__":
    app.run()
