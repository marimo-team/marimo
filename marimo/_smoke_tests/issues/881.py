# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.12"
app = marimo.App()


@app.cell
def __():
    import pandas as pd
    import marimo as mo
    df = pd.DataFrame({"data": [2.0]})
    mo.ui.table(df)
    return df, mo, pd


if __name__ == "__main__":
    app.run()
