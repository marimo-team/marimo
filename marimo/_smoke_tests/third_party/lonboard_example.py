# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==1.2.0",
#     "lonboard==0.10.4",
#     "marimo",
#     "polars==1.23.0",
#     "pyarrow==19.0.1",
#     "shapely==2.0.7",
#     "sqlglot==26.6.0",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="full")


@app.cell
def _():
    import duckdb
    from lonboard import viz

    # Initialize DuckDB connection
    con = duckdb.connect()

    # Load spatial extension
    duckdb.install_extension("spatial", connection=con)
    duckdb.load_extension("spatial", connection=con)
    return con, viz


@app.cell
def _(con):
    sql = """
        SELECT 'Polygon 1' AS polygon_name, 'POLYGON((-48.5 -25.4, -48.4 -25.4, -48.4 -25.3, -48.5 -25.3, -48.5 -25.4))'::geometry AS geometry
        UNION ALL
        SELECT 'Polygon 2' AS polygon_name, 'POLYGON((-48.3 -25.4, -48.2 -25.4, -48.2 -25.3, -48.3 -25.3, -48.3 -25.4))'::geometry AS geometry
        UNION ALL
        SELECT 'Polygon 3' AS polygon_name, 'POLYGON((-48.1 -25.4, -48.0 -25.4, -48.0 -25.3, -48.1 -25.3, -48.1 -25.4))'::geometry AS geometry
        UNION ALL
        SELECT 'Polygon 4' AS polygon_name, 'POLYGON((-48.55 -25.35, -48.45 -25.35, -48.45 -25.25, -48.55 -25.25, -48.55 -25.35))'::geometry AS geometry
        UNION ALL
        SELECT 'Polygon 5' AS polygon_name, 'POLYGON((-48.35 -25.35, -48.25 -25.35, -48.25 -25.25, -48.35 -25.25, -48.35 -25.35))'::geometry AS geometry
    """
    polygons = con.sql(sql)
    return (polygons,)


@app.cell
def _(con, polygons, viz):
    viz(polygons, con=con)
    return


if __name__ == "__main__":
    app.run()
