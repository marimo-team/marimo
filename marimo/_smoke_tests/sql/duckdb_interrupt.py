import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")


@app.cell
def _():
    FILE = "https://data.source.coop/cholmes/eurocrops/unprojected/geoparquet/FR_2018_EC21.parquet"
    return (FILE,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        INSTALL spatial;
        LOAD spatial;
        """
    )
    return


@app.cell
def _():
    10
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT 1;
        """
    )
    return


@app.cell
def _(FILE, mo, null):
    _df = mo.sql(
        f"""
        CREATE TABLE gdf AS
        SELECT * 
        FROM '{FILE}'
        """
    )
    return


if __name__ == "__main__":
    app.run()
