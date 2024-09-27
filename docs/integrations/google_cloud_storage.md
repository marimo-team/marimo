# Google Cloud Storage

## Getting Started

To use Google Cloud Storage as a data source, you will need to install the `google-cloud-storage` Python package. You can install this package using `pip`:

```bash
pip install google-cloud-storage
```

## Authentication

### Application Default Credentials (Recommended)

The easiest way to authenticate with Google Cloud Storage is to use [Application Default Credentials](https://cloud.google.com/docs/authentication/production). If you are running marimo on Google Cloud and your resource has a service account attached, then Application Default Credentials will automatically be used.
If you are running marimo locally, you can authenticate with Application Default Credentials by running the following command:

```bash
gcloud auth application-default login
```

### Service Account Key File

To authenticate with Google Cloud Storage, you will need to create a service account and download the service account key file. You can create a service account and download the key file by following the instructions [here](https://cloud.google.com/iam/docs/creating-managing-service-account-keys).

Once you have downloaded the key file, you can authenticate with Google Cloud Storage by setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of the key file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key/file.json
```

## Reading Data

To read data from Google Cloud Storage, you will need to create a `StorageClient` object. You can then use this object to read data from Google Cloud Storage.

```python
# Cell 1 - Load libraries
import marimo as mo
from google.cloud import storage

# Cell 2 - Load buckets
client = storage.Client()
buckets = client.list_buckets()

# Cell 3 - Select bucket
selected_bucket = mo.ui.dropdown(
    label="Select bucket", options=[b.name for b in buckets]
)
selected_bucket

# Cell 4 - Load files
files = list(bucket.list_blobs())
items = [
    {
        "Name": f.name,
        "Updated": f.updated.strftime("%h %d, %Y"),
        "Size": f.size,
    }
    for f in files
]
file_table = mo.ui.table(items, selection="single")
file_table if items else mo.md("No files found").callout()
```

## Example

Check out our full example using Google Cloud Storage [here](https://github.com/marimo-team/marimo/blob/main/examples/cloud/gcp/google_cloud_storage.py)

Or run it yourself:

```bash
marimo run https://raw.githubusercontent.com/marimo-team/marimo/main/examples/cloud/gcp/google_cloud_storage.py
```
