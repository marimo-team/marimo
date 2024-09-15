import marimo

__generated_with = "0.7.0"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(
        r"""
        # Electric Vehicle Population Data

        > This dataset shows the Battery Electric Vehicles (BEVs) and Plug-in Hybrid Electric Vehicles (PHEVs) that are currently registered through Washington State Department of Licensing (DOL).
        """
    )
    return


@app.cell
def __(mo):
    evs = mo.sql(
        f"""
        create or replace table evs as
            from 'https://datasets.marimo.app/gov/Electric_Vehicle_Population_Data.csv';
        select * from evs
        """
    )
    return evs,


@app.cell
def __(mo, years):
    all_years = years["Model Year"]
    year_select = mo.ui.multiselect.from_series(years["Model Year"])
    return all_years, year_select


@app.cell
def __(cities, mo):
    all_cities = cities["City"]
    city_select = mo.ui.multiselect.from_series(cities["City"])
    return all_cities, city_select


@app.cell
def __(makes, mo):
    all_makes = makes["Make"]
    make_select = mo.ui.multiselect.from_series(makes["Make"])
    return all_makes, make_select


@app.cell
def __(city_select, make_select, mo, year_select):
    mo.hstack([year_select, city_select, make_select], justify="space-between")
    return


@app.cell
def __(alt, grouped_by_city, mo):
    _chart = (
        alt.Chart(grouped_by_city)
        .mark_bar()
        .encode(
            y=alt.Y("City", type="nominal", sort="-x"),
            x=alt.X("sum(count)", type="quantitative"),
            color=alt.Color("Model Year", type="nominal"),
        )
        .properties(title="Top 10 City", width="container")
    )
    chart1 = mo.ui.altair_chart(_chart, chart_selection=False)
    return chart1,


@app.cell
def __(alt, grouped_by_make, mo):
    _chart = (
        alt.Chart(grouped_by_make)
        .mark_bar()
        .encode(
            y=alt.Y("Make", type="nominal", sort="-x"),
            x=alt.X("sum(count)", type="quantitative"),
            color=alt.Color("Model Year", type="nominal"),
        )
        .properties(title="Top 10 Make", width="container")
    )
    chart2 = mo.ui.altair_chart(_chart, chart_selection=False)
    return chart2,


@app.cell
def __(chart1, chart2, mo):
    mo.hstack([chart1, chart2], widths="equal")
    return


@app.cell
def __(mo):
    mo.md(r"## Appendix")
    return


@app.cell
def __(evs, mo):
    years = mo.sql(
        f"""
        SELECT DISTINCT CAST(evs."Model Year" AS VARCHAR) AS "Model Year" FROM evs;
        """
    )
    return years,


@app.cell
def __(evs, mo):
    cities = mo.sql(
        f"""
        SELECT DISTINCT CAST(evs."City" AS VARCHAR) AS "City" FROM evs WHERE "City" != 'null';
        """
    )
    return cities,


@app.cell
def __(evs, mo):
    makes = mo.sql(
        f"""
        SELECT DISTINCT CAST(evs."Make" AS VARCHAR) AS "Make" FROM evs;
        """
    )
    return makes,


@app.cell
def __(
    cast_to_ints,
    city_select,
    evs,
    make_select,
    mo,
    sql_list,
    year_select,
):
    grouped_by_city = mo.sql(
        f"""
        SELECT COUNT(*) AS "count", "City", "Model Year"
        FROM evs
        WHERE 
            {sql_list("Model Year", cast_to_ints(year_select.value))}
            AND 
            {sql_list("Make", make_select.value)}
            AND
            {sql_list("City", city_select.value)}
        GROUP BY "City", "Model Year"
        HAVING COUNT(*) > 1
        ORDER BY "count" DESC
        """
    )
    return grouped_by_city,


@app.cell
def __(
    cast_to_ints,
    city_select,
    evs,
    make_select,
    mo,
    sql_list,
    year_select,
):
    grouped_by_make = mo.sql(
        f"""
        SELECT COUNT(*) AS "count", "Make", "Model Year" 
        FROM evs
        WHERE 
            {sql_list("Model Year", cast_to_ints(year_select.value))}
            AND 
            {sql_list("Make", make_select.value)}
            AND
            {sql_list("City", city_select.value)}
        GROUP BY "Make", "Model Year"
        HAVING COUNT(*) > 1
        ORDER BY "count" DESC
        """
    )
    return grouped_by_make,


@app.cell
def __():
    def sql_list(column, items):
        if not items:
            return "True == True"
        literals = [as_literal(i) for i in items]
        return f"\"{column}\" IN ({','.join(literals)})"


    def as_literal(v):
        return f"'{v}'" if isinstance(v, str) else str(v)


    def cast_to_ints(items):
        return [int(i) for i in items]
    return as_literal, cast_to_ints, sql_list


@app.cell
def __():
    # Imports
    import marimo as mo
    import altair as alt
    return alt, mo


if __name__ == "__main__":
    app.run()
