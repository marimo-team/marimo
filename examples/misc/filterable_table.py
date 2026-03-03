# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Filterable DataFrame
    """)
    return


@app.cell
def _(pd):
    # Read the csv
    df = pd.read_json(data_url("cars.json"))
    return (df,)


@app.cell
def _(df):
    # Create options for select widgets
    manufacturer_options = df["Name"].str.split().str[0].unique()
    manufacturer_options.sort()
    cylinder_options = df["Cylinders"].unique().astype(str)
    cylinder_options.sort()
    return cylinder_options, manufacturer_options


@app.cell
def _(cylinder_options, df, manufacturer_options, mo):
    # Create the filters
    manufacturer = mo.ui.dropdown(manufacturer_options, label="Manufacturer")
    cylinders = mo.ui.dropdown(cylinder_options, label="Cylinders")

    horse_power = mo.ui.range_slider.from_series(
        df["Horsepower"],
        show_value=True,
    )

    mo.hstack([manufacturer, horse_power, cylinders], gap=3).left()
    return cylinders, horse_power, manufacturer


@app.cell
def _(df, filter_df):
    filter_df(df)
    return


@app.cell
def _(cylinders, horse_power, manufacturer):
    def filter_df(df):
        filtered_df = df
        if manufacturer.value:
            filtered_df = filtered_df[
                filtered_df["Name"].str.contains(manufacturer.value, case=False)
            ]
        if cylinders.value:
            filtered_df = filtered_df[filtered_df["Cylinders"] == cylinders.value]
        if horse_power.value:
            left, right = horse_power.value
            filtered_df = filtered_df[
                (filtered_df["Horsepower"] >= left)
                & (filtered_df["Horsepower"] <= right)
            ]
        return filtered_df

    return (filter_df,)


@app.function
def data_url(file):
    return f"https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/{file}"


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    return mo, pd


if __name__ == "__main__":
    app.run()
