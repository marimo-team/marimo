# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    minimum_units = mo.ui.slider(
        start=5,
        stop=20,
        value=10,
        label="Minimum units sold",
    )
    minimum_units
    return (minimum_units,)


@app.cell
def _(minimum_units, mo):
    sales = mo.sql(
        f"""
        WITH sales(region, product, units, unit_price) AS (
            VALUES
                ('Americas', 'Notebook', 12, 19.00),
                ('Asia', 'Notebook', 18, 18.50),
                ('Europe', 'Pen set', 9, 12.00),
                ('Oceania', 'Desk pad', 15, 24.00),
                ('Africa', 'Pen set', 7, 11.50)
        )
        SELECT
            region,
            product,
            units,
            ROUND(units * unit_price, 2) AS revenue
        FROM sales
        WHERE units >= {minimum_units.value}
        ORDER BY revenue DESC
        """
    )
    return (sales,)


if __name__ == "__main__":
    app.run()
