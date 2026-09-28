# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    records = [
        {"city": "Bangkok", "region": "Asia", "temperature_c": 31},
        {"city": "London", "region": "Europe", "temperature_c": 16},
        {"city": "Nairobi", "region": "Africa", "temperature_c": 24},
        {"city": "New York", "region": "Americas", "temperature_c": 21},
        {"city": "Sydney", "region": "Oceania", "temperature_c": 23},
        {"city": "Tokyo", "region": "Asia", "temperature_c": 22},
    ]
    return (records,)


@app.cell
def _(mo, records):
    regions = mo.ui.multiselect(
        options=sorted({row["region"] for row in records}),
        value=["Asia"],
        label="Regions",
    )
    regions
    return (regions,)


@app.cell
def _(mo, records, regions):
    filtered_records = [
        row
        for row in records
        if not regions.value or row["region"] in regions.value
    ]
    mo.ui.table(filtered_records, selection=None)
    return


if __name__ == "__main__":
    app.run()
