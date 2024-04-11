# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App(width="medium")


@app.cell
def __():
    import polars as pl
    from sklearn.datasets import fetch_california_housing

    housing = fetch_california_housing()
    df = pl.DataFrame(
        data=housing.data, schema=housing.feature_names
    ).with_columns(Price=housing.target)

    df.plot.scatter(x="MedInc", y="Price")
    return df, fetch_california_housing, housing, pl


if __name__ == "__main__":
    app.run()
