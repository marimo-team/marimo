# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "great-tables==0.17.0",
#     "marimo",
#     "polars==1.30.0",
# ]
# ///

import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # [Great-tables](https://github.com/posit-dev/great-tables) + marimo

    Adapted from https://github.com/machow/coffee-sales-data
    """)
    return


@app.cell
def _():
    import polars as pl
    import polars.selectors as cs
    import os
    import marimo as mo
    from pathlib import Path
    from great_tables import GT, loc, style

    current_dir = os.path.dirname(os.path.realpath(__file__))
    coffee_sales = pl.DataFrame.deserialize(
        Path(current_dir) / "coffee-sales.json", format="json"
    )
    return GT, coffee_sales, cs, loc, mo, pl, style


@app.cell
def _(coffee_sales, mo):
    revenue = mo.ui.range_slider.from_series(coffee_sales["revenue_dollars"])
    return (revenue,)


@app.cell(hide_code=True)
def _(mo, revenue):
    mo.hstack(
        [revenue, f"${revenue.value[0]:,.0f} - ${revenue.value[1]:,.0f}"]
    ).left()
    return


@app.cell(hide_code=True)
def _(coffee_sales, revenue):
    lower = revenue.value[0]
    upper = revenue.value[1]
    filterered_coffee_sales = coffee_sales.filter(
        (coffee_sales["revenue_dollars"] >= lower)
        & (coffee_sales["revenue_dollars"] <= upper)
    )
    return (filterered_coffee_sales,)


@app.cell(hide_code=True)
def _(GT, cs, filterered_coffee_sales, loc, pl, style):
    sel_rev = cs.starts_with("revenue")
    sel_prof = cs.starts_with("profit")

    coffee_table = (
        GT(filterered_coffee_sales)
        .tab_header("Sales of Coffee Equipment")
        .tab_spanner(label="Revenue", columns=sel_rev)
        .tab_spanner(label="Profit", columns=sel_prof)
        .cols_label(
            revenue_dollars="Amount",
            profit_dollars="Amount",
            revenue_pct="Percent",
            profit_pct="Percent",
            monthly_sales="Monthly Sales",
            icon="",
            product="Product",
        )
        # formatting ----
        .fmt_number(
            columns=cs.ends_with("dollars"),
            compact=True,
            pattern="${x}",
            n_sigfig=3,
        )
        .fmt_percent(columns=cs.ends_with("pct"), decimals=0)
        # style ----
        .tab_style(
            style=style.fill(color="aliceblue"),
            locations=loc.body(columns=sel_rev),
        )
        .tab_style(
            style=style.fill(color="papayawhip"),
            locations=loc.body(columns=sel_prof),
        )
        .tab_style(
            style=style.text(weight="bold"),
            locations=loc.body(rows=pl.col("product") == "Total"),
        )
        .fmt_nanoplot("monthly_sales", plot_type="bar")
        .sub_missing(missing_text="")
    )

    coffee_table
    return


if __name__ == "__main__":
    app.run()
