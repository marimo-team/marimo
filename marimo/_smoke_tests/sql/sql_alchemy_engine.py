import marimo

__generated_with = "0.10.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import sqlalchemy as sa
    return (sa,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""# Raw SQL with mo.sql()""")
    return


@app.cell
def _(sa):
    from sqlalchemy import text

    # Create an in-memory SQLite database
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.connect() as con:
        con.execute(
            text("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            category TEXT NOT NULL
        )
        """)
        )

        con.execute(
            text("""
        INSERT INTO products (name, price, category) VALUES
            ('Laptop', 999.99, 'Electronics'),
            ('Coffee Maker', 49.99, 'Appliances'),
            ('Headphones', 79.99, 'Electronics'),
            ('Toaster', 29.99, 'Appliances'),
            ('Smartphone', 599.99, 'Electronics'),
            ('Blender', 39.99, 'Appliances')
        """)
        )
        con.commit()
    return con, engine, text


@app.cell
def _(engine, mo, products):
    products = mo.sql(
        """
    SELECT name, price, category
    FROM products
    ORDER BY price DESC
    """,
        engine=engine,
    )
    return (products,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### All Products (sorted by price)""")
    return


@app.cell(hide_code=True)
def _(mo, products):
    mo.hstack(
        [
            products,
            mo.vstack(
                [
                    mo.md("### Summary"),
                    f"Total products: {len(products)}",
                    f"Average price: ${products['price'].mean():.2f}",
                ]
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Category Summary""")
    return


@app.cell
def _(engine, mo, products):
    mo.sql(
        """
    -- Category summary
    SELECT
        category,
        COUNT(*) as count,
        ROUND(AVG(price), 2) as avg_price,
        ROUND(MIN(price), 2) as min_price,
        ROUND(MAX(price), 2) as max_price
    FROM products
    GROUP BY category
    ORDER BY avg_price DESC
    """,
        engine=engine,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Interactive price filter
    price_threshold = mo.ui.slider(
        start=0, stop=1000, value=100, label="Max Price $"
    )
    mo.md(f"### Products under {price_threshold}")
    return (price_threshold,)


@app.cell
def _(engine, mo, price_threshold, products):
    mo.sql(
        f"""
    SELECT name, price, category
    FROM products
    WHERE price < {price_threshold.value}
    ORDER BY price DESC
    """,
        engine=engine,
    )
    return


if __name__ == "__main__":
    app.run()
