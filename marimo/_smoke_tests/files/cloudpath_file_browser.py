import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    file_browser = mo.ui.file_browser()
    file_browser
    return (file_browser,)


@app.cell
def _():
    BUCKET = "gs://public-datasets-deepmind-alphafold-v4/"
    # BUCKET = "s3://"
    # BUCKET = "az://bucket_name/"
    return (BUCKET,)


@app.cell
def _(BUCKET):
    from cloudpathlib import CloudPath

    # dispatches to S3Path based on prefix
    root_dir = CloudPath(BUCKET)
    root_dir
    return CloudPath, root_dir


@app.cell
def _(cloud_file_browser):
    cloud_file_browser.value
    return


@app.cell
def _(mo, root_dir):
    cloud_file_browser = mo.ui.file_browser(initial_path=root_dir, limit=10)
    cloud_file_browser
    return (cloud_file_browser,)


@app.cell
def _(cloud_file_browser):
    [f.path.is_dir() for f in cloud_file_browser.value]
    return


@app.cell
def _(cloud_file_browser):
    [type(f.path) for f in cloud_file_browser.value]
    return


@app.cell
def _(cloud_file_browser):
    [f.path for f in cloud_file_browser.value]
    return


@app.cell
def _(cloud_file_browser):
    [f.path.read_text() for f in cloud_file_browser.value]
    return


if __name__ == "__main__":
    app.run()
