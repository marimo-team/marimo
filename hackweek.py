import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium", layout_file="layouts/hackweek.canvas.json")


@app.cell
def _():
    import duckdb

    DATABASE_URL = ":memory:"
    engine = duckdb.connect(DATABASE_URL, read_only=False)
    return (engine,)


@app.cell
def _(engine, mo):
    _df = mo.sql(
        """
        SELECT * FROM "hf://datasets/scikit-learn/Fish/Fish.csv"
        """,
        engine=engine,
    )
    return


@app.cell
def _(engine, mo):
    credit_cards = mo.sql(
        """
        SELECT * FROM "hf://datasets/scikit-learn/credit-card-clients/UCI_Credit_Card.csv"
        """,
        engine=engine,
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import altair as alt

    return


if __name__ == "__main__":
    app.run()
