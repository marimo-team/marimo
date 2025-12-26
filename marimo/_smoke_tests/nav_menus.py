# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(mo):
    mo.md("""# Horizontal""")
    return


@app.cell
def _(mo):
    mo.nav_menu(
        {
            "#overview": "Overview",
            "#sales": f"{mo.icon('lucide:shopping-cart')} Sales",
            "#products": f"{mo.icon('lucide:package')} Products",
        }
    )
    return


@app.cell
def _(mo):
    mo.md("""-----""")
    return


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
    return


@app.cell
def _(mo):
    mo.md("""# Vertical""")
    return


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
    return


@app.cell
def _(mo):
    mo.md("""-----""")
    return


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
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
