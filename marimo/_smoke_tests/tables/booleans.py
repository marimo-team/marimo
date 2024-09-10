# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import pandas as pd

    data = {
        "A": [True, True, True],
        "B": [False, False, False],
        "C": [True, True, False],
    }

    df = pd.DataFrame(data)
    df
    return data, df, pd


if __name__ == "__main__":
    app.run()
