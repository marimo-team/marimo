# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.6"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Connect to AWS S3 Bucket""")
    return


@app.cell
def _():
    import boto3
    import pandas as pd
    from botocore.exceptions import NoCredentialsError

    # Initialize S3 client
    s3_client = boto3.client(
        "s3",
        aws_access_key_id="YOUR_ACCESS_KEY",
        aws_secret_access_key="YOUR_SECRET_KEY",
        region_name="us-east-1",  # Change to your region
    )

    # List buckets
    try:
        response = s3_client.list_buckets()
        buckets = [bucket["Name"] for bucket in response["Buckets"]]
        print("Available buckets:", buckets)
    except NoCredentialsError:
        print("Credentials not available")
    return NoCredentialsError, boto3, buckets, pd, response, s3_client


@app.cell
def _(pd, s3_client):
    # Example: Read CSV file from S3
    bucket_name = "your-bucket-name"
    file_key = "path/to/your/file.csv"

    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        df = pd.read_csv(obj["Body"])
        df.head()
    except Exception as e:
        print(f"Error: {e}")
    return bucket_name, df, file_key, obj


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
