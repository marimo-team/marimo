# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(np):
    import pandas as pd

    df = pd.DataFrame([np.random.randn(20)]*10, columns=np.arange(20))
    df
    return (df,)


@app.cell
def _(df):
    # Series
    df[0]
    return


@app.cell
def _():
    import numpy as np
    return (np,)


if __name__ == "__main__":
    app.run()
