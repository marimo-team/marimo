import marimo

__generated_with = "0.6.22"
app = marimo.App(width="medium")


@app.cell
def __(cars, slider):
    some_cars = cars[cars["Cylinders"] == slider.value]
    return some_cars,


@app.cell
def __(cars):
    type(cars["Cylinders"])
    return


@app.cell
def __():
    import altair as alt
    from vega_datasets import data

    import marimo as mo
    return alt, data, mo


@app.cell
def __(data, mo):
    cars = data.cars()

    min = cars["Cylinders"].min()
    max = cars["Cylinders"].max()
    slider = mo.ui.slider(min,max,show_value=True,label="Cylinders",debounce=True)
    slider
    return cars, max, min, slider


@app.cell
def __(mo, slider):
    mo.sql(
        f"""
        SELECT "Name", "Miles_per_Gallon", "Cylinders", "Horsepower"
        FROM cars
        WHERE "Cylinders" = {slider.value}
        """
    )
    return


@app.cell
def __(alt, mo, some_cars):
    mo.ui.altair_chart(
        alt.Chart(some_cars).mark_point().encode(
            x="Miles_per_Gallon", y="Horsepower")
        .properties(height=200))
    return


if __name__ == "__main__":
    app.run()
