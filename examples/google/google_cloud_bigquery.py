import marimo

__generated_with = "0.1.43"
app = marimo.App(width="full")


@app.cell
def __():
    # Imports
    import marimo as mo
    import os
    from google.cloud import bigquery
    return bigquery, mo, os


@app.cell
def __(mo):
    mo.md(
        f"""
    # Google Cloud BigQuery

    Required dependencies:
    ```sh
    $ pip install google-cloud-bigquery db-dtypes
    ```
    """
    )
    return


@app.cell
def __(mo):
    # Configuration
    credentials = mo.ui.text(label="(Optional) Path to credentials file").form()
    mo.accordion(
        {
            "⚙️ Configuration": mo.md(
                f"""
                This app requires a Google Cloud Platform account and a bucket to access. You will need to be authenticated with `gcloud auth login`, 
                or provide a path to a credentials file.

                {credentials}
                 """
            )
        }
    )
    return credentials,


@app.cell
def __(bigquery, credentials, os):
    # Set up client
    if credentials.value:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials.value
    else:
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    client = bigquery.Client()
    datasets = list(client.list_datasets())
    return client, datasets


@app.cell
def __(datasets, mo):
    # Dataset selection
    selected_dataset = mo.ui.dropdown(
        label="Select dataset", options=[d.dataset_id for d in datasets]
    )
    selected_dataset
    return selected_dataset,


@app.cell
def __(client, mo, selected_dataset):
    mo.stop(not selected_dataset.value)

    dataset = client.dataset(selected_dataset.value)
    return dataset,


@app.cell
def __(client, dataset, mo):
    # Table selection
    tables = list(client.list_tables(dataset))
    selected_table = mo.ui.dropdown(
        label="Select table", options=[t.table_id for t in tables]
    )
    selected_table
    return selected_table, tables


@app.cell
def __(client, dataset, mo, selected_table):
    results = client.list_rows(dataset.table(selected_table.value), max_results=10)
    mo.ui.table(results.to_dataframe(), selection=None)
    return results,


if __name__ == "__main__":
    app.run()
