# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Reshaping Data

        This snippet demonstrates reshaping data in Polars using `pivot()` and `unpivot()` 
        operations for transforming between wide and long formats.

        Example: `df.pivot(values="value", index=["date"], on="category")`
        """
    )
    return


@app.cell
def _():
    import polars as pl
    import numpy as np

    # Create sample data
    df = pl.DataFrame(
        {
            "date": ["2024-01-01"] * 4 + ["2024-01-02"] * 4,
            "category": ["A", "B"] * 4,
            "metric": ["sales", "profit"] * 4,
            "value": np.random.randint(100, 1000, 8),
        }
    )

    # Reshaping operations
    # 1. Pivot wider
    pivoted = df.pivot(
        values="value",
        index=["date", "category"],
        on="metric",
        aggregate_function="first",
    )

    # 2. Unpivot longer
    unpivoted = pivoted.unpivot(
        index=["date", "category"],
        on=["sales", "profit"],
        value_name="value",
        variable_name="metric",
    )
    unpivoted
    return df, np, pivoted, pl, unpivoted


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
