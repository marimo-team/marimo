import marimo

__generated_with = "0.9.10"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE SCHEMA IF NOT EXISTS f1;

        CREATE OR REPLACE TABLE f1.races AS
        FROM read_csv('https://docs.google.com/spreadsheets/d/1unpDUkTx8UVhuO0bo2yyC4RrAHNhxGnzJziLu5jeXvw/export?format=csv&gid=2031195234');

        CREATE OR REPLACE TABLE f1.constructors AS
        FROM read_csv('https://docs.google.com/spreadsheets/d/1unpDUkTx8UVhuO0bo2yyC4RrAHNhxGnzJziLu5jeXvw/export?format=csv&gid=0');

        CREATE OR REPLACE TABLE f1.constructor_results AS
        FROM read_csv('https://docs.google.com/spreadsheets/d/1unpDUkTx8UVhuO0bo2yyC4RrAHNhxGnzJziLu5jeXvw/export?format=csv&gid=1549360536');
        """
    )
    return (f1,)


@app.cell
def __(constructor_results, constructors, f1, mo, races):
    constructor_champions = mo.sql(
        f"""
        SELECT
            c."name" as constructor_name,
            r.year::text as year,
            sum(cr.points) as points_scored,
            count(*) as races
        FROM f1.constructor_results cr
        LEFT JOIN f1.races r on r.raceid = cr.raceid
        LEFT JOIN f1.constructors c on c.constructorid = cr.constructorid
        GROUP BY ALL
        HAVING points_scored > 0
        ORDER BY points_scored desc
        """
    )
    return (constructor_champions,)


@app.cell
def __(constructor_champions, pl):
    winners_py_year = (
        constructor_champions.group_by("year")
        .agg(pl.col("points_scored").max())
        .join(constructor_champions, on=["year", "points_scored"], how="left")
        .select(["year", "constructor_name", "points_scored"])
        .sort("year")
    )
    return (winners_py_year,)


@app.cell
def __(mo):
    num_years = mo.ui.slider(30, 60, label="Number of years", show_value=True)
    num_years
    return (num_years,)


@app.cell
def __(alt, num_years, pl, winners_py_year):
    # Take the last 30 years
    year = 2024 - num_years.value
    _winners_py_year = winners_py_year.filter(pl.col("year").cast(pl.Int32) > year)

    chart = (
        alt.Chart(_winners_py_year)
        .mark_circle()
        .encode(
            x="year",
            y="constructor_name",
            color="constructor_name",
            size=alt.Size("points_scored", scale=alt.Scale(range=[40, 1000])),
        )
        .properties(title="Total Points Scored by Constructor")
    )

    chart
    return chart, year


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import altair as alt
    return alt, mo, pl


@app.cell
def __(alt, chart, constructor_champions, mo, pl):
    constructor_champions_yearly = (
        constructor_champions.group_by(["year"])
        .agg(pl.col("points_scored").sum().alias("total_points"))
        .sort("year")
    )

    chart2 = (
        alt.Chart(constructor_champions_yearly)
        .mark_line()
        .encode(
            x="year",
            y=alt.Y("total_points", scale=alt.Scale(range=[0, 1000])),
            color="year",
            tooltip=["year", "total_points"],
        )
        .properties(title="Total Points Scored by Year")
    )

    chart2

    constructor_champions_top5 = (
        constructor_champions.top_k(5, by="points_scored")
        .select(["constructor_name", "points_scored"])
        .sort("points_scored", descending=True)
    )

    chart3 = (
        alt.Chart(constructor_champions_top5)
        .mark_bar()
        .encode(
            x=alt.X("constructor_name", sort="-y"),
            y="points_scored",
            color="constructor_name",
            tooltip=["constructor_name", "points_scored"],
        )
        .properties(title="Top 5 Constructors by Total Points Scored")
    )

    chart3

    constructor_champions_avg_points = (
        constructor_champions.group_by("constructor_name")
        .agg(pl.col("points_scored").mean().alias("avg_points"))
        .sort("avg_points", descending=True)
    )

    chart4 = (
        alt.Chart(constructor_champions_avg_points)
        .mark_bar()
        .encode(
            x=alt.X("constructor_name", sort="-y"),
            y="avg_points",
            color="constructor_name",
            tooltip=["constructor_name", "avg_points"],
        )
        .properties(title="Average Points Scored by Constructor")
    )

    mo.vstack([chart, chart2, chart3, chart4])
    return (
        chart2,
        chart3,
        chart4,
        constructor_champions_avg_points,
        constructor_champions_top5,
        constructor_champions_yearly,
    )


if __name__ == "__main__":
    app.run()
