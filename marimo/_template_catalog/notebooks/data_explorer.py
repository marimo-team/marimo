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
    temperatures = {
        "Bangkok": 31,
        "London": 16,
        "Nairobi": 24,
        "Tokyo": 22,
    }
    return (temperatures,)


@app.cell
def _(mo, temperatures):
    city = mo.ui.dropdown(
        options=list(temperatures),
        value="Bangkok",
        label="City",
    )
    city
    return (city,)


@app.cell
def _(city, mo, temperatures):
    temperature = temperatures[city.value]
    mo.md(f"## {city.value}\n\nSample temperature: **{temperature}°C**")
    return


if __name__ == "__main__":
    app.run()
