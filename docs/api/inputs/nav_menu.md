# Navigation Menu

/// marimo-embed
    size: large

```python
@app.cell
def __():
    nav_menu = mo.nav_menu({
        "/overview": "Overview",
        "Sales": {
            "/sales": {
                "label": "Sales",
                "description": "View sales and revenue",
            },
            "/sales/invoices": {
                "label": "Invoices",
                "description": "View invoices and payments",
            },
            "/sales/customers": {
                "label": "Customers",
                "description": "View customers and subscriptions",
            },
        },
        "Products": {
            "/products": {
                "label": "Products",
                "description": "View and manage products",
            },
            "/products/inventory": {
                "label": "Inventory",
                "description": "View inventory and stock levels",
            },
            "/products/categories": {
                "label": "Categories",
                "description": "View categories and products",
            },
        },
    })
    nav_menu
    return
```

///

::: marimo.nav_menu
