# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "google-cloud-storage==2.18.2",
#     "marimo",
#     "protobuf==5.28.2",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    # Imports
    import marimo as mo
    import os
    from google.cloud import storage

    return mo, os, storage


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


@app.cell
def _(credentials, mo, os, project, storage):
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

    client = storage.Client(project=_project)
    buckets = client.list_buckets()
    return buckets, client


@app.cell
def _(buckets, mo):
    # Bucket selection
    selected_bucket = mo.ui.dropdown(
        label="Select bucket", options=[bucket.name for bucket in buckets]
    )
    selected_bucket
    return (selected_bucket,)


@app.cell
def _(mo):
    get_prefix, set_prefix = mo.state("")
    return get_prefix, set_prefix


@app.cell
def _(client, mo, selected_bucket):
    mo.stop(not selected_bucket.value)

    bucket = client.get_bucket(selected_bucket.value)
    return (bucket,)


@app.cell
def _(bucket, get_prefix):
    _prefix = get_prefix() or None
    blobs = list(bucket.list_blobs(max_results=30, prefix=_prefix))
    return (blobs,)


@app.cell
def _(get_prefix, mo, set_prefix):
    output = None
    _prefix = get_prefix()
    if _prefix:
        output = mo.hstack(
            [
                mo.md(f"Showing files in: **`{_prefix}`**"),
                mo.ui.button(label="Clear", on_click=lambda _: set_prefix(None)),
            ]
        )
    output
    return


@app.cell
def _(blobs, bucket, mo, set_prefix):
    # Display files in a table
    _files = [
        {
            "Filter": mo.ui.button(
                label="Filter",
                on_change=lambda _: set_prefix(blob.name),
                value=blob.name,
            )
            if blob.name.endswith("/")
            else None,
            "Name": blob.name,
            "Updated": blob.updated.strftime("%h %d, %Y"),
            "Url": mo.Html(
                f'<a href="https://storage.cloud.google.com/{bucket.name}/{blob.name}" target="_blank">🔗 Link</a>'
            ),
            "Size": blob.size,
        }
        for blob in blobs
    ]
    file_table = mo.ui.table(_files, selection="single")
    file_table if _files else mo.md("No files found").callout()
    return (file_table,)


@app.cell
def _(bucket, file_table, mo):
    # Load selected file
    if len(file_table.value) >= 1:
        _selected_file = file_table.value[0]
        _blob = bucket.get_blob(_selected_file["Name"])
        if (
            _blob.content_type and _blob.content_type.startswith("image")
        ) or _blob.name.endswith(".png"):
            mo.output.replace(mo.image(_blob.download_as_string()))
        else:
            mo.output.replace(mo.plain_text(_blob.download_as_text()))
    return


if __name__ == "__main__":
    app.run()
