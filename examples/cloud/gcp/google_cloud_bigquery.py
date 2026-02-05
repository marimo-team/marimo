# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "db-dtypes==1.3.0",
#     "google-cloud-bigquery==3.25.0",
#     "marimo",
#     "protobuf==5.28.2",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    from google.cloud import bigquery

    return bigquery, mo, os


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Google Cloud BigQuery
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Configuration
    credentials = mo.ui.text(placeholder="path/to/creds.json")
    mo.md(
        f"""
        ## **⚙ Configuration**

        This app requires a Google Cloud Platform account and a bucket to access.

        Authenticate with `gcloud auth login`, or provide a path to a credentials
        file: {credentials}
        """
    )
    return (credentials,)


@app.cell(hide_code=True)
def _(mo):
    project = mo.ui.text(label="gcloud project")
    project
    return (project,)


@app.cell(hide_code=True)
def _(bigquery, credentials, mo, os, project):
    # Set up client
    if credentials.value:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials.value
    else:
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    if project.value is not None:
        _project = project.value
    else:
        _project = os.env.get("GCLOUD_PROJECT")

    mo.stop(not _project, mo.md("☝️ Provide a gcloud project."))
    client = bigquery.Client(project=_project)
    datasets = list(client.list_datasets())
    return client, datasets


@app.cell
def _(datasets, mo):
    # Dataset selection
    selected_dataset = mo.ui.dropdown(
        label="Select dataset", options=[d.dataset_id for d in datasets]
    )
    selected_dataset
    return (selected_dataset,)


@app.cell
def _(client, mo, selected_dataset):
    mo.stop(not selected_dataset.value)

    dataset = client.dataset(selected_dataset.value)
    return (dataset,)


@app.cell
def _(client, dataset, mo):
    # Table selection
    tables = list(client.list_tables(dataset))
    selected_table = mo.ui.dropdown(
        label="Select table", options=[t.table_id for t in tables]
    )
    selected_table
    return (selected_table,)


@app.cell
def _(client, dataset, mo, selected_table):
    results = client.list_rows(dataset.table(selected_table.value), max_results=10)
    mo.ui.table(results.to_dataframe(), selection=None)
    return


if __name__ == "__main__":
    app.run()
