# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.6"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Connect to Google Cloud Storage Bucket""")
    return


@app.cell
def _():
    from google.cloud import storage
    import pandas as pd

    # Initialize GCS client
    # Note: This assumes you have set up authentication
    # (either through service account JSON or application default credentials)
    storage_client = storage.Client()

    # List buckets
    try:
        buckets = list(storage_client.list_buckets())
        print("Available buckets:", [bucket.name for bucket in buckets])
    except Exception as e:
        print(f"Error listing buckets: {e}")
    return buckets, pd, storage, storage_client


@app.cell
def _(pd, storage_client):
    # Example: Read CSV file from GCS
    bucket_name = "your-bucket-name"
    blob_name = "path/to/your/file.csv"

    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Download to a string and create DataFrame
        content = blob.download_as_string()
        df = pd.read_csv(pd.io.common.BytesIO(content))
        df.head()
    except Exception as e:
        print(f"Error: {e}")
    return blob, blob_name, bucket, bucket_name, content, df


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
