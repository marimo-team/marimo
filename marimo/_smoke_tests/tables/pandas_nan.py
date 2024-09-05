# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.8.11"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import numpy as np

    # This shouldn't print a runtime warning
    df = pd.DataFrame({"a": [1,2,3], "b": [np.nan, np.nan, np.nan]})
    df
    return df, mo, np, pd


if __name__ == "__main__":
    app.run()
