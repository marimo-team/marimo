# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "pandas==2.2.3",
#     "requests==2.32.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # 🤗 Hugging Face dataset search and exploration

    This notebook allows you to search and explore the datasets available on Hugging Face.
    First you can search for a dataset using the filters provided. Then you can select a dataset and explore the parquet files that are available for that dataset. Finally you can use the SQL editor to query the parquet files and the dataframe editor to explore the results of your query.
    """)
    return


@app.cell(hide_code=True)
def _(fetch_hugging_face_datasets, mo, pd):
    # Load the datasets
    with mo.status.spinner(
        title="Loading datasets from Hugging Face",
    ):
        datasets = fetch_hugging_face_datasets()
        # Fix lastModified column to be a date from a str
        datasets["lastModified"] = pd.to_datetime(datasets["lastModified"])
    return (datasets,)


@app.cell(hide_code=True)
def _(datasets, duckdb):
    # Extract info from the datasets
    all_tags = (
        duckdb.sql("""SELECT DISTINCT tags FROM datasets WHERE tags IS NOT NULL""")
        .df()["tags"]
        .explode()
        .unique()
    )

    dataset_length = len(datasets)

    dataset_date_range = f"{print_month_year(datasets.lastModified.min().date())} - {print_month_year(datasets.lastModified.max().date())}"
    return all_tags, dataset_date_range, dataset_length


@app.cell(hide_code=True)
def _(all_tags, dataset_date_range, dataset_length, mo):
    # Create stats cards
    stats = mo.hstack(
        [
            mo.stat(
                value=str(dataset_length),
                label="Datasets",
                caption="Number of datasets fetched from Hugging Face",
            ),
            mo.stat(
                label="Date Range",
                value=dataset_date_range,
            ),
            mo.stat(
                value=str(len(all_tags)),
                label="Tags",
                caption="Number of tags",
            ),
        ]
    )
    return (stats,)


@app.cell
def _(all_tags, mo, stats):
    # Search filters
    search_filter = mo.ui.text_area(
        label="Search",
        placeholder="Search for a dataset",
        value="",
    )
    tag_filter = mo.ui.dropdown(all_tags[:10], label="Tag", full_width=True)
    mo.hstack(
        [stats, search_filter, tag_filter],
        justify="start",
        gap=2,
        widths=[2, 1, 1],
    )
    return search_filter, tag_filter


@app.cell(hide_code=True)
def _(datasets, duckdb, mo, search_filter, tag_filter):
    # Filter and display the datasets in a table
    datasets
    _fields = [
        "id",
        "lastModified",
        "downloads",
        # "tags",
        "author",
        "description",
    ]
    _statement = f"""SELECT {",".join(_fields)} FROM datasets"""
    _wheres = []
    if search_filter.value:
        _wheres.append(
            f"(description LIKE '%{search_filter.value}%' OR id LIKE '%{search_filter.value}%')"
        )
    if tag_filter.value and len(tag_filter.value) > 0:
        _wheres.append(f"tags LIKE '%{tag_filter.value}%'")

    if len(_wheres) > 0:
        _statement += " WHERE " + " AND ".join(_wheres)

    table = mo.ui.table(
        duckdb.sql(_statement).df(),
        selection="single",
        label="Datasets",
        page_size=5,
        pagination=True,
    )
    table
    return (table,)


@app.cell
def _(table):
    selected_dataset = (
        table.value.iloc[0]
        if table.value is not None and len(table.value)
        else None
    )
    return (selected_dataset,)


@app.cell
def _(mo, selected_dataset):
    mo.stop(selected_dataset is None)

    mo.md(
        f"""
    ---------

    ## Selected dataset: **{selected_dataset.id}**

    > {selected_dataset.description or "no description"}

    Downloads: _{selected_dataset.downloads}_

    You can select one of the parquet files below to load it into duckdb.
    """
    )
    return


@app.cell
def _(load_hugging_face_dataset, mo, selected_dataset):
    # Load the selected dataset's parquet files
    mo.stop(selected_dataset is None)

    with mo.status.spinner(
        title="Loading datasets from Hugging Face",
    ):
        _data = load_hugging_face_dataset(selected_dataset.id)
    selected_parquet = mo.ui.table(
        _data,
        label="Files",
        selection="single",
        page_size=5,
        pagination=True,
    )
    selected_parquet
    return (selected_parquet,)


@app.cell
def _(selected_parquet):
    has_selected_file = (
        selected_parquet.value is not None and len(selected_parquet.value) > 0
    )
    url = selected_parquet.value[0] if has_selected_file else None
    return has_selected_file, url


@app.cell
def _(duckdb, mo, url):
    # Load the selected parquet into duckdb

    mo.stop(not url)

    with mo.status.spinner(
        title="Loading parquet file into duckdb",
        subtitle="This may take a sec",
    ):
        con = duckdb.connect()
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        # Fetch num rows
        _rows = con.sql(f"SELECT COUNT(*) FROM '{url}'").df()
        # Fetch column names
        _columns = con.sql(f"SELECT * FROM '{url}' LIMIT 0").df().columns

    mo.hstack(
        [
            mo.stat(
                value=str(_rows.iloc[0, 0]),
                label="Rows",
                caption="Number of rows in the dataset",
            ),
            mo.stat(
                value=str(len(_columns)),
                label="Columns",
                caption="Number of columns in the dataset",
            ),
            mo.stat(
                value=", ".join(list(_columns)),
                label="Columns",
            ),
        ],
        widths=[1, 1, 2],
    )
    return (con,)


@app.cell
def _(has_selected_file, mo, render_sql_editor):
    mo.stop(not has_selected_file)

    sql_editor = render_sql_editor()
    mo.vstack(
        [
            mo.md(
                """
    ## SQL Editor

    You can query this dataset using SQL. The SQL query will be executed in duckdb. You can use the `$dataset` variable to reference the dataset's parquet files. For example:

    ```sql
    SELECT * FROM '$dataset' LIMIT 10
    ```
    """
            ),
            sql_editor,
        ]
    )
    return (sql_editor,)


@app.cell
def _(has_selected_file, mo, render_sql_results, sql_editor):
    mo.stop(not has_selected_file)

    render_sql_results(sql_editor)
    return


@app.cell
def _(datasets, mo, render_dataframe_editor):
    mo.stop(len(datasets) == 0)

    df_editor = render_dataframe_editor()

    mo.vstack(
        [
            mo.md(
                """
    ## Dataframe Editor

    You can explore the dataset using the dataframe editor below. The dataframe editor is powered by [mo.ui.dataframe](https://docs.marimo.io/api/inputs/dataframe.html)
    """
            ),
            df_editor,
        ]
    )
    return


@app.cell
def _(con, mo, url):
    # UI renderers


    def render_sql_editor():
        return mo.ui.text_area(
            placeholder="SELECT * FROM '$dataset' LIMIT 10",
            value="SELECT * FROM '$dataset' LIMIT 10",
            full_width=True,
        ).form()


    def render_sql_results(sql_editor):
        sql = sql_editor.value
        if sql is None or len(sql) == 0:
            return None
        return mo.ui.table(
            con.sql(sql.replace("$dataset", url)).df(),
            selection=None,
            page_size=10,
            pagination=True,
        )


    def render_dataframe_editor(limit=500):
        data = con.sql(f"SELECT * FROM '{url}' LIMIT {limit}").df()
        df_editor = mo.ui.dataframe(data)
        return df_editor

    return render_dataframe_editor, render_sql_editor, render_sql_results


@app.function
# Utils


def print_month_year(date):
    return date.strftime("%b %Y")


@app.cell
def _(functools, json, pd, requests):
    # Cached requests


    @functools.lru_cache
    def fetch_hugging_face_datasets():
        url = "https://huggingface.co/api/datasets"
        response = requests.get(url)
        data = json.loads(response.text)
        return pd.DataFrame(data)


    @functools.lru_cache
    def load_hugging_face_dataset(dataset_id):
        r = requests.get(
            "https://datasets-server.huggingface.co/parquet?dataset=blog_authorship_corpus"
        )
        j = r.json()
        urls = [f["url"] for f in j["parquet_files"]]
        return urls

    return fetch_hugging_face_datasets, load_hugging_face_dataset


@app.cell
def _():
    import requests
    import json
    import functools
    import marimo as mo
    import duckdb
    import pandas as pd

    return duckdb, functools, json, mo, pd, requests


if __name__ == "__main__":
    app.run()
