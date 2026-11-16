import marimo

__generated_with = "0.25.2"
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


@app.cell
def _():
    10


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT 1;
        """
    )


@app.cell
def _(FILE: str, mo):
    _df = mo.sql(
        f"""
        CREATE TABLE gdf AS
        SELECT * 
        FROM '{FILE}'
        """
    )


if __name__ == "__main__":
    app.run()
