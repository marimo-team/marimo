import marimo

__generated_with = "0.7.1"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    cars = mo.sql(
        f"""
        -- Download a CSV and create an in-memory table
        CREATE OR replace TABLE cars as
        FROM 'https://datasets.marimo.app/cars.csv';
        SELECT Make, Model, Cylinders, Weight, MPG_City from cars;
        """
    )
    return cars,


@app.cell
def __(cars):
    # We can reference the output variable as a dataframe in python
    [len(cars), cars["MPG_City"].mean()]
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
