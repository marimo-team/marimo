# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.6"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Using fsspec with Cloud Storage (S3 & GCS)""")
    return


@app.cell
def _():
    import fsspec
    return (fsspec,)


@app.cell
def _(fsspec):
    # Create filesystem objects
    s3 = fsspec.filesystem(
        "s3",
        key="YOUR_ACCESS_KEY",  # AWS credentials
        secret="YOUR_SECRET_KEY",
        client_kwargs={"region_name": "us-east-1"},
    )

    # List buckets/files
    s3_files = s3.ls("your-bucket-name")
    print("S3 files:", s3_files[:5])  # Show first 5 files
    return s3, s3_files


@app.cell
def _(fsspec):
    # Create filesystem objects
    gcs = fsspec.filesystem(
        "gcs",
        # GCS will use default credentials from environment
        token=None,
    )

    # List buckets/files
    gcs_files = gcs.ls("your-gcs-bucket")
    print("GCS files:", gcs_files[:5])  # Show first 5 files
    return gcs, gcs_files


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
