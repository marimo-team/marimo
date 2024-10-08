# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __(happiness_index, mo, pd):
    df = pd.read_csv(happiness_index)
    mo.ui.table(
        df, 
        freeze_columns_left=["Country name", "Ladder score"], 
        freeze_columns_right=["Standard error of ladder score"]
    )
    return df,


@app.cell
def __(df, mo):
    mo.ui.table(df)
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    happiness_index = 'https://raw.githubusercontent.com/MainakRepositor/Datasets/master/World%20Happiness%20Data/2020.csv'
    return happiness_index, mo, pd


if __name__ == "__main__":
    app.run()
