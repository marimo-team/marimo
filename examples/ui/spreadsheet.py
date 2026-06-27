# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
# ]
# ///
import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo
    return pd, mo


@app.cell
def _(mo):
    mo.md(
        """
        # Interactive Spreadsheet & Python Integration

        This example demonstrates how to call Python code and run functions on your spreadsheet data, and how to push updates from the Python environment back into the spreadsheet.
        """
    )
    return


@app.cell
def _(pd):
    # Initial dataset representing inventory
    initial_df = pd.DataFrame({
        "Product": ["Laptop", "Mouse", "Keyboard", "Monitor"],
        "Category": ["Electronics", "Accessories", "Accessories", "Electronics"],
        "Price": [999.99, 25.50, 79.99, 299.99],
        "Quantity": [5, 20, 15, 8],
    })
    return (initial_df,)


@app.cell
def _(initial_df, mo):
    # Setup state so we can push data back to the spreadsheet from Python
    get_data, set_data = mo.state(initial_df)
    return get_data, set_data


@app.cell
def _(get_data, mo):
    # Instantiate the spreadsheet bound to the state variable
    sheet = mo.ui.spreadsheet(get_data(), label="Inventory Spreadsheet")
    sheet
    return (sheet,)


@app.cell
def _(mo):
    mo.md(
        """
        ### Pattern 1: Call Python functions on spreadsheet values (Reactive Downstream)
        The function below runs in Python on the edited spreadsheet data and adds computed columns (`Subtotal`, `Tax`, and `Total`) in real-time.
        """
    )
    return


@app.cell
def _(sheet):
    # A Python function that performs calculations on the spreadsheet data
    def calculate_totals(df):
        processed = df.copy()
        # Ensure correct column data types before calculation
        try:
            processed["Price"] = processed["Price"].astype(float)
            processed["Quantity"] = processed["Quantity"].astype(float)
            processed["Subtotal"] = processed["Price"] * processed["Quantity"]
            processed["Tax"] = processed["Subtotal"] * 0.08
            processed["Total"] = processed["Subtotal"] + processed["Tax"]
        except Exception:
            pass
        return processed
    return (calculate_totals,)


@app.cell
def _(calculate_totals, mo, sheet):
    # Call the python function reactively on sheet.value
    df_with_totals = calculate_totals(sheet.value)

    # Compute summaries in Python
    try:
        total_items = int(df_with_totals["Quantity"].sum())
        total_value = df_with_totals["Total"].sum()

        dashboard = mo.vstack([
            mo.hstack([
                mo.stat(label="Total Items", value=f"{total_items}"),
                mo.stat(label="Total Value (inc. Tax)", value=f"${total_value:,.2f}"),
            ], justify="start", gap=4),
            mo.md("#### Computed DataFrame View:"),
            mo.ui.table(df_with_totals, selection=None)
        ])
    except Exception as e:
        dashboard = mo.md(f"Error executing calculations: {e}")

    dashboard
    return dashboard, total_items, total_value


@app.cell
def _(mo):
    mo.md(
        """
        ### Pattern 2: Push changes from Python to the Spreadsheet
        Click the button below to execute a Python function that applies a **10% discount** to all items in the inventory and writes the updated values back into the spreadsheet cells.
        """
    )
    return


@app.cell
def _(mo, set_data, sheet):
    def apply_discount(btn):
        # 1. Get the current spreadsheet data frame
        df = sheet.value.copy()
        try:
            # 2. Modify the prices in Python
            df["Price"] = (df["Price"].astype(float) * 0.9).round(2)
            # 3. Update the state to write the modified data back into the spreadsheet
            set_data(df)
        except Exception:
            pass

    discount_button = mo.ui.button(
        label="Apply 10% Discount in Python",
        on_click=apply_discount,
        kind="warn"
    )
    discount_button
    return apply_discount, discount_button


if __name__ == "__main__":
    app.run()
