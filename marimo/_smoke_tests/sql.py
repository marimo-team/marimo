import marimo

__generated_with = "0.6.25"
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
    mo.md("## Cars")
    return


@app.cell
def __(data, mo):
    cars = data.cars()
    cylinders = mo.ui.slider.from_series(cars["Cylinders"])
    cylinders
    return cars, cylinders


@app.cell
def __(cylinders, mo):
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
    mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="Miles_per_Gallon", y="Horsepower")
        .properties(height=200)
    )
    return


@app.cell
def __(mo):
    mo.md("## Airports")
    return


@app.cell
def __(data):
    airports = data.airports()
    return airports,


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        select * from airports limit 10
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("Debug")
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


if __name__ == "__main__":
    app.run()
