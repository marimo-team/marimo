# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "polars==1.34.0",
#     "requests==2.32.5",
# ]
# ///

import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    return (pl,)


@app.cell
def _(pl):
    # Enums and categorical data types
    bears_enum = pl.Enum(["Polar", "Panda", "Brown"])
    bears = pl.Series(
        ["Polar", "Panda", "Brown", "Brown", "Polar"] * 30, dtype=bears_enum
    )

    enums_cats = pl.DataFrame(
        {
            "bears": ["Polar", "Panda", "Brown", "Brown", "Polar"] * 30,
            "bears_cat": ["Polar", "Panda", "Brown", "Brown", "Polar"] * 30,
        },
        schema={
            "bears": bears_enum,
            "bears_cat": pl.Categorical,
        },
    )
    enums_cats
    return


@app.cell
def _(pl):
    pokemon_url = "https://gist.githubusercontent.com/armgilles/194bcff35001e7eb53a2a8b441e8b2c6/raw/92200bc0a673d5ce2110aaad4544ed6c4010f687/pokemon.csv"
    pl.read_csv(pokemon_url)
    return


@app.cell
def _(pl):
    import io
    import requests
    import zipfile

    train_parquet_link = "https://www.kaggle.com/api/v1/datasets/download/shahmirvarqha/train-stations-amsterdam"

    response = requests.get(train_parquet_link)
    zip_data = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_data) as z:
        # List files to find parquet file, assuming one parquet file is in the archive
        parquet_file_name = [f for f in z.namelist() if f.endswith(".parquet")][0]
        with z.open(parquet_file_name) as parquet_file:
            trains_df = pl.read_parquet(parquet_file)

    trains_df[:20000]
    return


if __name__ == "__main__":
    app.run()
