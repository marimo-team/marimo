import marimo

__generated_with = "0.18.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import polars as pl

    decimal_data = pl.DataFrame(
        {"decimals": pl.Series(range(201), dtype=pl.Decimal(scale=2))}
    )
    decimal_data
    return


@app.cell
def _():
    import pandas as pd
    from decimal import Decimal

    pandas_decimal_data = pd.DataFrame(
        {"decimals": [Decimal(i) / Decimal("100") for i in range(201)]}
    )
    pandas_decimal_data
    return


if __name__ == "__main__":
    app.run()
