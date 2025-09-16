# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "duckdb==1.1.3",
#     "marimo",
#     "polars==1.21.0",
#     "psycopg[binary]==3.2.4",
#     "sqlglot==26.3.9",
#     "sqlmodel==0.0.22",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""# SQLModel with `mo.sql()`""")
    return


@app.cell
def _():
    from sqlmodel import text, create_engine
    return (create_engine,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## sqlite""")
    return


@app.cell
def _(create_engine, mo):
    # Create an in-memory SQLite database
    sqlite = create_engine("sqlite:///:memory:")

    mo.sql("DROP TABLE IF EXISTS products;", engine=sqlite)

    mo.sql(
        """
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        price DECIMAL(10,2) NOT NULL,
        category TEXT NOT NULL
    );
    """,
        engine=sqlite,
    )

    mo.sql(
        """
    INSERT INTO products (name, price, category) VALUES
        ('Laptop', 999.99, 'Electronics'),
        ('Coffee Maker', 49.99, 'Appliances'),
        ('Headphones', 79.99, 'Electronics'),
        ('Toaster', 29.99, 'Appliances'),
        ('Smartphone', 599.99, 'Electronics'),
        ('Blender', 39.99, 'Appliances');
    """,
        engine=sqlite,
    )
    return (sqlite,)


@app.cell
def _(mo, sqlite):
    products_df = mo.sql(
        f"""
        SELECT name, price, category
        FROM products
        ORDER BY price DESC
        """,
        engine=sqlite
    )
    return (products_df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### All Products (sorted by price)""")
    return


@app.cell(hide_code=True)
def _(mo, products_df):
    mo.hstack(
        [
            products_df,
            mo.vstack(
                [
                    mo.md("### Summary"),
                    f"Total products: {len(products_df)}",
                    f"Average price: ${products_df['price'].mean():.2f}",
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
def _(mo, sqlite):
    _df = mo.sql(
        f"""
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
        engine=sqlite
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
def _(mo, price_threshold, sqlite):
    _df = mo.sql(
        f"""
        SELECT name, price, category
        FROM products
        WHERE price < {price_threshold.value}
        ORDER BY price DESC
        """,
        engine=sqlite
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## postgresql""")
    return


@app.cell
def _(mo):
    import os

    psql_url = mo.ui.text(
        kind="password",
        label="PostgreSQL URL",
        placeholder="postgresql://",
        value=os.getenv("POSTGRES_URL") or "",
    )
    psql_url
    return (psql_url,)


@app.cell
def _(create_engine, mo, psql_url):
    mo.stop(not psql_url.value)

    normalized_url = psql_url.value.replace(
        "postgres://", "postgresql+psycopg://"
    ).replace("postgresql://", "postgresql+psycopg://")

    # Create a PostgreSQL database
    my_postgres = create_engine(normalized_url)
    return (my_postgres,)


@app.cell
def _(mo, my_postgres):
    _df = mo.sql(
        f"""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
        """,
        engine=my_postgres
    )
    return


@app.cell
def _(connection, mo):
    _df = mo.sql(
        f"""
        SELECT 1
        """,
        engine=connection
    )
    return


@app.cell
def _(mo, sqlite):
    _df = mo.sql(
        f"""
        SELECT * FROM products LIMIT 100
        """,
        engine=sqlite
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE foo AS
        FROM 'hf://datasets/julien040/hacker-news-posts/story.parquet' LIMIT 500
        """
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT "id" FROM memory.main.foo LIMIT 100
        """
    )
    return


if __name__ == "__main__":
    app.run()
