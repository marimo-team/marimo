import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __():
    from vega_datasets import data
    return (data,)


@app.cell
def __(data):
    cars = data.cars()
    cars
    return (cars,)


@app.cell
def __(cars, mo):
    mo.ui.table(
        cars,
        text_justify_columns={
            "Name": "left",
            "Miles_per_Gallon": "center",
            "Cylinders": "right",
        },
        wrapped_columns=["Name", "Cylinders"],
    )
    return


if __name__ == "__main__":
    app.run()
