# Google Cloud BigQuery

## Getting Started

To use Google Cloud BigQuery as a data source, you will need to install the `google-cloud-bigquery` Python package. You can install this package using `pip`:

```bash
pip install google-cloud-bigquery db-dtypes
```

## Authentication

### Application Default Credentials (Recommended)

The easiest way to authenticate with Google Cloud BigQuery is to use [Application Default Credentials](https://cloud.google.com/docs/authentication/production). If you are running marimo on Google Cloud and your resource has a service account attached, then Application Default Credentials will automatically be used.
If you are running marimo locally, you can authenticate with Application Default Credentials by running the following command:

```bash
gcloud auth application-default login
```

### Service Account Key File

To authenticate with Google Cloud BigQuery, you will need to create a service account and download the service account key file. You can create a service account and download the key file by following the instructions [here](https://cloud.google.com/iam/docs/creating-managing-service-account-keys).

Once you have downloaded the key file, you can authenticate with Google Cloud BigQuery by setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of the key file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key/file.json
```

## Reading Data

To read data from Google Cloud BigQuery, you will need to create a `BigQueryClient` object. You can then use this object to read data from Google Cloud BigQuery.

```python
# Cell 1 - Load libraries
import marimo as mo
from google.cloud import bigquery

# Cell 2 - Load datasets
client = bigquery.Client()
datasets = list(client.list_datasets())

# Cell 3 - Select dataset
selected_dataset = mo.ui.dropdown(
    label="Select dataset", options=[d.dataset_id for d in datasets]
)
selected_dataset

# Cell 4 - Load tables
dataset = client.dataset(selected_dataset.value)
tables = list(client.list_tables(dataset))
selected_table = mo.ui.dropdown(
    label="Select table", options=[t.table_id for t in tables]
)
selected_table

# Cell 5 - Load table data
results = client.list_rows(dataset.table(selected_table.value), max_results=10)
mo.ui.table(results.to_dataframe(), selection=None)
```

## Example

Check out our full example using Google Cloud BigQuery [here](https://github.com/marimo-team/marimo/blob/main/examples/cloud/gcp/google_cloud_bigquery.py)

Or run it yourself:

```bash
marimo run https://raw.githubusercontent.com/marimo-team/marimo/main/examples/cloud/gcp/google_cloud_bigquery.py
```
