import marimo

__generated_with = "0.7.14"
app = marimo.App(width="medium")


@app.cell
def __(data):
    # Load the cars dataset
    cars_df = data.cars()
    cars_df["Year"] = cars_df["Year"].apply(lambda x: x.year)
    return cars_df,


@app.cell
def __(cars_df, mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE cars AS SELECT * FROM cars_df;
        """
    )
    return


@app.cell
def __(cars_df, mo):
    origin = mo.ui.dropdown.from_series(cars_df["Origin"])
    year_range = mo.ui.range_slider.from_series(cars_df["Year"], show_value=True)
    top_n = mo.ui.number(value=5, start=1, stop=50, label="Top N Cars")
    mo.hstack([origin, year_range, top_n])
    return origin, top_n, year_range


@app.cell
def __(origin):
    origin_filter = (
        f"AND Origin = '{origin.value}'" if origin.value != None else ""
    )
    return origin_filter,


@app.cell
def __(mo, origin, top_n):
    mo.md(
        f"""##Top {top_n.value} Cars {f"in {origin.value}" if origin.value != None else ""} """
    )
    return


@app.cell
def __(mo, origin_filter, top_n, year_range):
    _df = mo.sql(
        f"""
        SELECT Name, Year, Origin, Horsepower, Miles_per_Gallon,
               Acceleration, Weight_in_lbs
        FROM cars
        WHERE Year BETWEEN {year_range.value[0]} AND {year_range.value[1]}
        {origin_filter}
        ORDER BY Horsepower DESC
        LIMIT {top_n.value}
        """
    )
    return


@app.cell
def __(mo):
    mo.md("""### Breakdown by Origin""")
    return


@app.cell
def __(cars, mo, year_range):
    _df = mo.sql(
        f"""
        WITH ranked_cars AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY Origin ORDER BY Horsepower DESC) as rank,
                   AVG(Horsepower) OVER (PARTITION BY Origin) as avg_horsepower,
                   AVG(Miles_per_Gallon) OVER (PARTITION BY Origin) as avg_mpg
            FROM cars
            WHERE Year BETWEEN {year_range.value[0]} AND {year_range.value[1]}
        )
        SELECT Origin,
               ROUND(avg_horsepower, 2) as Avg_Horsepower,
               ROUND(avg_mpg, 2) as Avg_MPG,
               FIRST(Name) as Top_Car,
               FIRST(Horsepower) as Top_Horsepower
        FROM ranked_cars
        WHERE rank = 1
        GROUP BY Origin, avg_horsepower, avg_mpg
        ORDER BY Avg_Horsepower DESC
        """
    )
    return


@app.cell
def __(alt, duckdb, mo, year_range):
    _query = f"""
    SELECT Year, 
           AVG(Horsepower) as Avg_Horsepower, 
           AVG(Miles_per_Gallon) as Avg_MPG
    FROM cars
    WHERE Year BETWEEN {year_range.value[0]} AND {year_range.value[1]}
    GROUP BY Year
    ORDER BY Year
    """
    _data = duckdb.sql(_query).df()

    base = alt.Chart(_data).encode(x="Year:T")

    line1 = base.mark_line(color="red").encode(
        y=alt.Y("Avg_Horsepower:Q", axis=alt.Axis(title="Average Horsepower"))
    )

    line2 = base.mark_line(color="blue").encode(
        y=alt.Y("Avg_MPG:Q", axis=alt.Axis(title="Average MPG"))
    )

    _chart = (
        alt.layer(line1, line2)
        .resolve_scale(y="independent")
        .properties(
            width="container",
            height=400,
            title="Trend of Average Horsepower and MPG over Time",
        )
    )
    mo.ui.altair_chart(_chart, chart_selection=None)
    return base, line1, line2


@app.cell(hide_code=True)
def __(alt, duckdb, mo, year_range):
    _query = f"""
    SELECT Horsepower, Miles_per_Gallon, Origin
    FROM cars
    WHERE Year BETWEEN {year_range.value[0]} AND {year_range.value[1]}
    """
    _data = duckdb.sql(_query).df()

    _chart = (
        alt.Chart(_data)
        .mark_point()
        .encode(
            x="Horsepower:Q",
            y="Miles_per_Gallon:Q",
            color="Origin:N",
            tooltip=["Horsepower:Q", "Miles_per_Gallon:Q", "Origin:N"],
        )
        .properties(height=400, title="Horsepower vs Miles per Gallon by Origin")
    )

    chart = mo.ui.altair_chart(_chart)
    chart
    return chart,


@app.cell
def __(chart, mo):
    mo.stop(chart.value.empty, mo.callout("Select cars from the chart above."))
    selected_cars = chart.value
    return selected_cars,


@app.cell(hide_code=True)
def __(aggs, aggs_selected, mo):
    def title_case(title):
        return title.title().replace("_", " ")


    def diff(column):
        value = (aggs_selected[column][0] - aggs[column][0]) / aggs_selected[
            column
        ][0]
        percent = f"{value * 100:.2f}%"
        return percent


    mo.hstack(
        [
            mo.stat(
                label=title_case(column),
                value=aggs_selected[column][0],
                bordered=True,
                caption=f"Total: {aggs[column][0]}",
            )
            for column in aggs.columns
        ]
    )
    return diff, title_case


@app.cell(hide_code=True)
def __(cars, mo, selected_cars):
    aggs_selected = mo.sql("""
    SELECT 
        COUNT(*) as count,
        AVG(Horsepower) as avg_horsepower,
        AVG(Miles_per_Gallon) as avg_mpg,
        MIN(Horsepower) as min_horsepower,
        MAX(Horsepower) as max_horsepower,
        MIN(Miles_per_Gallon) as min_mpg,
        MAX(Miles_per_Gallon) as max_mpg
    FROM selected_cars
    """)
    aggs = mo.sql("""
    SELECT 
        COUNT(*) as count,
        AVG(Horsepower) as avg_horsepower,
        AVG(Miles_per_Gallon) as avg_mpg,
        MIN(Horsepower) as min_horsepower,
        MAX(Horsepower) as max_horsepower,
        MIN(Miles_per_Gallon) as min_mpg,
        MAX(Miles_per_Gallon) as max_mpg
    FROM cars
    """)
    mo.output.clear()
    return aggs, aggs_selected


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import duckdb
    import altair as alt
    from vega_datasets import data
    return alt, data, duckdb, mo, pd


if __name__ == "__main__":
    app.run()
