# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(np):
    import pandas as pd

    df = pd.DataFrame([np.random.randn(20)]*10, columns=np.arange(20))
    df
    return df, pd


@app.cell
def __(df):
    # Series
    df[0]
    return


@app.cell
def __():
    import numpy as np
    return np,


if __name__ == "__main__":
    app.run()
