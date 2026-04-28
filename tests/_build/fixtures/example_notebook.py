import marimo

__generated_with = "0.0.0"
app = marimo.App()


@app.cell
def _imports():
    import marimo as mo

    return (mo,)


@app.cell
def customers(mo):
    customers = mo.sql("SELECT 1 AS id, 'alice' AS name")
    return (customers,)


@app.cell
def _users(mo):
    users = mo.sql("SELECT 1 AS id, 'admin' AS role")
    return (users,)


@app.cell
def orders_enriched(mo, users, customers):
    orders_enriched = mo.sql(
        "SELECT c.id, c.name, u.role "
        "FROM customers c LEFT JOIN users u ON c.id = u.id"
    )
    return (orders_enriched,)


@app.cell
def settings():
    settings = {"version": 1, "default_limit": 10}
    return (settings,)


@app.cell
def category(mo):
    category = mo.ui.dropdown(["a", "b"])
    return (category,)


@app.cell
def filtered(mo, orders_enriched, category):
    filtered = mo.sql(
        f"SELECT * FROM orders_enriched WHERE name = '{category.value}'"
    )
    return (filtered,)


if __name__ == "__main__":
    app.run()
