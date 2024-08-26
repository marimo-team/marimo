import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def __(mo, pd):
    df = pd.read_csv('https://raw.githubusercontent.com/MainakRepositor/Datasets/master/World%20Happiness%20Data/2020.csv')
    mo.ui.table(df, freeze_columns_right=["Country name"])
    return df,


if __name__ == "__main__":
    app.run()
