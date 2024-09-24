# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
# ]
# ///
import marimo

__generated_with = "0.7.18"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        # SQLite!

        You can use marimo's SQL cells to read from (and write to) SQLite databases.

        The first step is to attach a SQLite database. We attach to a sample database in a read-only mode below.
        """
    )
    return


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        -- boilerplate: detach the database so this cell works when you re-run it
        DETACH DATABASE IF EXISTS chinook;
        -- attach the database; omit READ_ONLY if you want to write to the database.
        ATTACH 'Chinook_Sqlite.sqlite' as chinook (TYPE SQLITE, READ_ONLY);

        SELECT table_name FROM INFORMATION_SCHEMA.TABLES where table_catalog == 'chinook';
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Once the database is attached, you can query it with SQL. For example, the next cell computes the average track length of each composer in the chinook database.""")
    return


@app.cell
def __(mo, track):
    _df = mo.sql(
        f"""
        SELECT composer, MEAN(Milliseconds) as avg_track_ms from chinook.track GROUP BY composer ORDER BY avg_track_ms DESC;
        """
    )
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo


    def download_sample_data():
        import os
        import requests

        url = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
        filename = "Chinook_Sqlite.sqlite"
        if not os.path.exists(filename):
            print("Downloading the Chinook database ...")
            response = requests.get(url)
            with open(filename, "wb") as f:
                f.write(response.content)
        else:
            print("Using cached database.")


    download_sample_data()
    return download_sample_data, mo


if __name__ == "__main__":
    app.run()
