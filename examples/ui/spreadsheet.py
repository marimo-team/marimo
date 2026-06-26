# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.23.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo

    return mo, pd


@app.cell
def _(mo):
    mo.md("""
    # Interactive Spreadsheet Example

    This example demonstrates how to use the interactive spreadsheet component `mo.ui.spreadsheet`.

    Double-click cells to edit them, insert/delete rows or columns, and see the downstream cells reactively recalculate Python variables instantly.
    """)
    return


@app.cell
def _(pd):
    # Initial DataFrame representing a simple sales log
    initial_df = pd.DataFrame({
        "Product": ["Laptop", "Mouse", "Keyboard", "Monitor"],
        "Category": ["Electronics", "Accessories", "Accessories", "Electronics"],
        "Price": [999.99, 25.50, 79.99, 299.99],
        "Quantity": [5, 20, 15, 8],
    })
    return (initial_df,)


@app.cell
def _(initial_df, mo):
    # Create the interactive spreadsheet UI element
    sheet = mo.ui.spreadsheet(initial_df, label="Inventory Spreadsheet")
    sheet
    return (sheet,)


@app.cell
def _(mo, sheet):
    # Reactive downstream cell utilizing the mutated DataFrame
    df = sheet.value

    # Calculate key metrics dynamically
    try:
        total_items = int(df["Quantity"].sum())
        total_value = (df["Price"] * df["Quantity"]).sum()
        avg_price = df["Price"].mean()

        stats = mo.vstack([
            mo.md("### Real-Time Statistics"),
            mo.hstack([
                mo.stat(label="Total Items", value=f"{total_items}"),
                mo.stat(label="Total Inventory Value", value=f"${total_value:,.2f}"),
                mo.stat(label="Average Price", value=f"${avg_price:.2f}"),
            ], justify="start", gap=4),
            mo.md("#### Updated Python DataFrame:"),
            mo.ui.table(df, selection=None)
        ])
    except Exception as e:
        stats = mo.md(
            f"**Error calculating statistics:** *{e}*\n\n"
            "Please make sure the 'Price' and 'Quantity' columns exist and contain numeric data."
        )

    stats
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
