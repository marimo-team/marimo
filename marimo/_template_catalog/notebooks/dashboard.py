# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full")


@app.cell
def _():
    import altair as alt
    import marimo as mo

    return alt, mo


@app.cell
def _():
    sales = [
        {"region": "Americas", "product": "Notebook", "revenue": 228},
        {"region": "Asia", "product": "Notebook", "revenue": 333},
        {"region": "Europe", "product": "Pen set", "revenue": 108},
        {"region": "Oceania", "product": "Desk pad", "revenue": 360},
        {"region": "Africa", "product": "Pen set", "revenue": 81},
        {"region": "Asia", "product": "Desk pad", "revenue": 288},
    ]
    return (sales,)


@app.cell
def _(mo, sales):
    region = mo.ui.dropdown(
        options=["All", *sorted({row["region"] for row in sales})],
        value="All",
        label="Region",
    )
    return (region,)


@app.cell
def _(region, sales):
    filtered_sales = [
        row
        for row in sales
        if region.value == "All" or row["region"] == region.value
    ]
    total_revenue = sum(row["revenue"] for row in filtered_sales)
    return filtered_sales, total_revenue


@app.cell
def _(alt, filtered_sales, mo, region, total_revenue):
    revenue_chart = (
        alt.Chart(alt.Data(values=filtered_sales))
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("product:N", title=None, sort="-y"),
            y=alt.Y("sum(revenue):Q", title="Revenue ($)"),
            color=alt.Color("product:N", legend=None),
            tooltip=["product:N", alt.Tooltip("sum(revenue):Q", format=",")],
        )
        .properties(height=240, width="container")
    )
    mo.vstack(
        [
            mo.md("# Sales dashboard"),
            region,
            mo.hstack(
                [
                    mo.stat(label="Revenue", value=f"${total_revenue:,.0f}"),
                    mo.stat(label="Orders", value=str(len(filtered_sales))),
                ]
            ),
            revenue_chart,
            mo.ui.table(filtered_sales, selection=None),
        ],
        gap=2,
    )
    return


if __name__ == "__main__":
    app.run()
