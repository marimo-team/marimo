# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.8.8"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import pandas as pd

    sample_df = pd.DataFrame(
        {
            "Name": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "City": ["New York", "Los Angeles", "Chicago"],
        }
    )
    return pd, sample_df


@app.cell
def __(mo, sample_df):
    import time

    mo.output.replace(sample_df)
    time.sleep(5)
    return time,


if __name__ == "__main__":
    app.run()
