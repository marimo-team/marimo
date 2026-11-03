# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _(mo):
    mo.md("""
    # Horizontal
    """)


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#overview": "Overview",
            "#sales": f"{mo.icon('lucide:shopping-cart')} Sales",
            "#products": f"{mo.icon('lucide:package')} Products",
        }
    )


@app.cell
def _(mo):
    mo.md("""
    -----
    """)


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#overview": "Overview",
            f"{mo.icon('lucide:shopping-cart')} Sales": {
                "/sales-today": "Sales today",
                "/sales-yesterday": "Sales yesterday",
                "/sales-custom": {
                    "label": "Custom",
                    "description": "Create custom filters to query sales",
                },
            },
            f"{mo.icon('lucide:package')} Products": {
                "#products-today": "Products today",
                "#products-yesterday": "Products yesterday",
                "#products-custom": {
                    "label": "Custom",
                    "description": "Create custom filters to query products",
                },
            },
        }
    )


@app.cell
def _(mo):
    mo.md("""
    # Vertical
    """)


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#overview": "Overview",
            "#sales": f"{mo.icon('lucide:shopping-cart')} Sales",
            "#products": f"{mo.icon('lucide:package')} Products",
        },
        orientation="vertical",
    )


@app.cell
def _(mo):
    mo.md("""
    -----
    """)


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#overview": "Overview",
            "Sales": {
                "#sales-today": "Sales today",
                "#sales-yesterday": "Sales yesterday",
                "#sales-custom": {
                    "label": "Custom",
                    "description": "Create custom filters to query sales",
                },
            },
            "Products": {
                "#products-today": "Products today",
                "#products-yesterday": "Products yesterday",
                "#products-custom": {
                    "label": "Custom",
                    "description": "Create custom filters to query products",
                },
            },
        },
        orientation="vertical",
    )


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
