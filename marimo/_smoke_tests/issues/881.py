# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import pandas as pd
    import marimo as mo
    df = pd.DataFrame({"data": [2.0]})
    mo.ui.table(df)
    return


if __name__ == "__main__":
    app.run()
