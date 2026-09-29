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
        {"region": "Americas", "product": "Notebook", "revenue": 228},
        {"region": "Asia", "product": "Notebook", "revenue": 333},
        {"region": "Europe", "product": "Pen set", "revenue": 108},
        {"region": "Oceania", "product": "Desk pad", "revenue": 360},
        {"region": "Africa", "product": "Pen set", "revenue": 81},
        {"region": "Asia", "product": "Desk pad", "revenue": 288},
    ]
    return (records,)


@app.cell
def _(mo, records):
    regions = mo.ui.multiselect(
        options=sorted({row["region"] for row in records}),
        value=["Asia"],
        label="Regions",
    )
    mo.vstack([mo.md("# Filter and summarize data"), regions])
    return (regions,)


@app.cell
def _(mo, records, regions):
    filtered_records = [
        row
        for row in records
        if not regions.value or row["region"] in regions.value
    ]
    sales_table = mo.ui.table(filtered_records, selection="multi")
    sales_table
    return (sales_table,)


@app.cell
def _(mo, sales_table):
    selected_revenue = sum(row["revenue"] for row in sales_table.value)
    mo.md(
        f"**Selected:** {len(sales_table.value)} rows · "
        f"**Revenue:** ${selected_revenue:,.0f}"
    )
    return


if __name__ == "__main__":
    app.run()
