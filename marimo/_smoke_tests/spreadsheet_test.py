import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo
    return pd, mo


@app.cell
def _(pd):
    df = pd.DataFrame({
        "Product": ["Apple", "Banana", "Cherry"],
        "Price": [1.2, 0.8, 2.5],
        "Quantity": [10, 20, 15]
    })
    return (df,)


@app.cell
def _(df, mo):
    mo.md("### Edit values in the interactive FortuneSheet spreadsheet:")
    return


@app.cell
def _(df, mo):
    sheet = mo.ui.spreadsheet(df, label="Sales Sheet")
    sheet
    return (sheet,)


@app.cell
def _(mo, sheet):
    edited_df = sheet.value
    
    try:
        total_quantity = edited_df["Quantity"].sum()
        revenue = (edited_df["Price"] * edited_df["Quantity"]).sum()
        
        output = mo.vstack([
            mo.md(f"**Total Quantity:** {total_quantity}"),
            mo.md(f"**Total Revenue:** ${revenue:.2f}"),
            mo.ui.table(edited_df)
        ])
    except Exception as e:
        output = mo.md(f"Error calculating: {e}")
        
    output
    return (edited_df, output)


if __name__ == "__main__":
    app.run()
