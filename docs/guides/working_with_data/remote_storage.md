# Remote Storage

marimo makes it easy to work with cloud storage and remote filesystems by automatically detecting [obstore](https://developmentseed.org/obstore/) and [fsspec](https://filesystem-spec.readthedocs.io/) storage connections in your notebook. From the Files panel, you can browse directories, search entries, copy URLs, and download files—all without leaving the editor.

<div align="center">
<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-remote-storage.mp4" type="video/mp4">
</video>
</div>

## Supported libraries

marimo auto-discovers variables that are instances of:

| Library | Base class | Example stores |
|---------|-----------|----------------|
| [obstore](https://developmentseed.org/obstore/) | `obstore.store.ObjectStore` | `S3Store`, `GCSStore`, `AzureStore`, `HTTPStore`, `LocalStore`, `MemoryStore` |
| [fsspec](https://filesystem-spec.readthedocs.io/) | `fsspec.AbstractFileSystem` | `S3FileSystem`, `GithubFileSystem`, `FTPFileSystem`, `DatabricksFileSystem`, and [many more](https://filesystem-spec.readthedocs.io/en/latest/api.html#built-in-implementations) |
| [huggingface_hub](https://huggingface.co/docs/huggingface_hub) | `huggingface_hub.HfApi` | Browse the Hugging Face Hub (datasets, models, spaces, buckets) |


## Creating a storage connection

You can either create a storage connection using the UI or code.

### 1. Using the UI

From the Files panel in the sidebar, expand the **Remote Storage** section and click the **Add remote storage** button. The UI will guide you through entering your storage connection details.

<div align="center">
  <figure>
    <img width="700" src="/_static/docs-add-remote-storage-ui.png" alt="Add a storage connection through the UI" />
  </figure>
</div>

If you'd like to connect to a storage that isn't supported by the UI, you can use the code method below, or submit a [feature request](https://github.com/marimo-team/marimo/issues/new?title=Add%20new%20storage%20connection%20UI:&labels=enhancement&template=feature_request.yaml).


### 2. Using code

#### obstore

```python
from obstore.store import S3Store

store = S3Store.from_url(
    "s3://my-bucket",
    access_key_id="...",
    secret_access_key="...",
)
```

S3-compatible stores can also authenticate with container-vended credentials — used by ECS/EKS task roles and CoreWeave sandboxes, where the platform injects a credential endpoint and a token file:

```python
import os

from obstore.store import S3Store

store = S3Store(
    "my-bucket",
    endpoint="https://my-bucket.cwobject.com",
    virtual_hosted_style_request=True,
    container_credentials_full_uri=os.environ["AWS_CONTAINER_CREDENTIALS_FULL_URI"],
    container_authorization_token_file=os.environ["AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE"],
)
```

!!! note "S3 endpoint gotchas"

    - `AWS_ENDPOINT_URL_S3` takes precedence over the `endpoint` argument, so an
      explicitly configured endpoint is silently ignored when that variable is set.
    - `virtual_hosted_style_request=True` expects the bucket name to already be part
      of the endpoint hostname; unlike boto3, obstore does not prepend it.

#### fsspec

```python
from fsspec.implementations.github import GithubFileSystem

repo = GithubFileSystem(org="marimo-team", repo="marimo")
```

#### Hugging Face Hub

```python
from huggingface_hub import HfApi

hf = HfApi()  # optional: HfApi(token=os.environ.get("HF_TOKEN"))
```

Use `hf://` URLs in Polars, pandas, or DuckDB to read files you find in the panel:

```python
df = pl.read_csv("hf://datasets/scikit-learn/Fish/Fish.csv")
```

After the cell runs, the **Remote Storage** section will populate with your connection, its detected protocol, and root path.

<div align="center">
  <figure>
    <img width="700" src="/_static/docs-remote-storage-panel.png" alt="Remote storage panel" />
  </figure>
</div>

## Multiple connections

You can have multiple storage connections in the same notebook — each one appears as a separate namespace. The panel header shows the variable name so you can tell them apart.

```python
from obstore.store import S3Store

prod = S3Store.from_url("s3://prod-bucket")
staging = S3Store.from_url("s3://staging-bucket")
```
