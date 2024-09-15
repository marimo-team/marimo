# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "vega-datasets",
#     "marimo",
#     "altair",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import altair as alt
    from vega_datasets import data
    import duckdb
    import marimo as mo
    return alt, data, duckdb, mo


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## Cars""")
    return


@app.cell
def __(data, mo):
    # Create a slider with the range of car cylinders
    cars = data.cars()
    cylinders = mo.ui.slider.from_series(cars["Cylinders"])
    cylinders
    return cars, cylinders


@app.cell
def __(cars, cylinders, mo):
    df = mo.sql(
        f"""
        SELECT "Name", "Miles_per_Gallon", "Cylinders", "Horsepower"
        FROM cars
        WHERE "Cylinders" = {cylinders.value}
        """
    )
    return df,


@app.cell
def __(alt, df, mo):
    # Chart the filtered cars
    mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="Miles_per_Gallon", y="Horsepower")
        .properties(height=200)
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## Airports""")
    return


@app.cell
def __(data):
    airports = data.airports()
    return airports,


@app.cell
def __(airports, mo):
    less_airports = mo.sql(
        f"""
        select * from airports limit 2
        """
    )
    return less_airports,


@app.cell
def __(less_airports):
    len(less_airports)
    return


@app.cell
def __(mo):
    mo.md("""## Google Sheets""")
    return


@app.cell
def __():
    sheet = "https://docs.google.com/spreadsheets/export?format=csv&id=1GuEPkwjdICgJ31Ji3iUoarirZNDbPxQj_kf7fd4h4Ro"
    return sheet,


@app.cell
def __(mo, sheet):
    job_types = mo.sql(
        f"""
        SELECT DISTINCT current_job_title
        FROM read_csv_auto('{sheet}', normalize_names=True)
        """
    )
    return job_types,


@app.cell
def __(job_types, mo):
    job_title = mo.ui.dropdown.from_series(job_types["current_job_title"])
    job_title
    return job_title,


@app.cell
def __(job_title, mo, sheet):
    _df = mo.sql(
        f"""
        SELECT *
        FROM read_csv_auto('{sheet}', normalize_names=True)
        WHERE current_job_title == '{job_title.value}'
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""Debug""")
    return


@app.cell(hide_code=True)
def __(duckdb):
    duckdb.get_table_names(
        f"""
        SELECT "Name", "Miles_per_Gallon", "Cylinders", "Horsepower"
        FROM cars
        """
    )
    return


@app.cell(hide_code=True)
def __(duckdb, job_title, sheet):
    duckdb.get_table_names(
        f"""
        SELECT *
        FROM read_csv_auto('{sheet}', normalize_names=True)
        WHERE current_job_title == '{job_title.value}'
        """
    )
    return


@app.cell
def __(cars, mo):
    grouped_cars_by_origin = mo.sql(
        """
        SELECT "Origin", COUNT(*) AS "Count"
        FROM cars
        GROUP BY "Origin"
        LIMIT 100
        """
    )
    return grouped_cars_by_origin,


if __name__ == "__main__":
    app.run()
