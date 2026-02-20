# Remote Storage

marimo makes it easy to work with cloud storage and remote filesystems by automatically detecting [Obstore](https://developmentseed.org/obstore/) and [fsspec](https://filesystem-spec.readthedocs.io/) storage connections in your notebook. From the **Remote Storage** panel in the sidebar, you can browse directories, search entries, copy URLs, and download files without leaving the editor.

!!! example "Experimental"

    Remote storage is an experimental feature. Enable it in **Settings > Experimental > Storage Inspector**.

<div align="center">
<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-remote-storage.mp4" type="video/mp4">
</video>
</div>

## Supported libraries

marimo auto-discovers variables that are instances of:

| Library | Base class | Example stores |
|---------|-----------|----------------|
| [Obstore](https://developmentseed.org/obstore/) | `obstore.store.ObjectStore` | `S3Store`, `GCSStore`, `AzureStore`, `HTTPStore`, `LocalStore`, `MemoryStore` |
| [fsspec](https://filesystem-spec.readthedocs.io/) | `fsspec.AbstractFileSystem` | `S3FileSystem`, `GithubFileSystem`, `FTPFileSystem`, `DatabricksFileSystem`, and [many more](https://filesystem-spec.readthedocs.io/en/latest/api.html#built-in-implementations) |


## Quick start

Create a storage connection in any cell. marimo will pick it up automatically after the cell executes.

### Obstore

```python
from obstore.store import S3Store

store = S3Store.from_url(
    "s3://my-bucket",
    access_key_id="...",
    secret_access_key="...",
)
```

### fsspec

```python
from fsspec.implementations.github import GithubFileSystem

repo = GithubFileSystem(org="marimo-team", repo="marimo")
```

After the cell runs, the **Remote Storage** section in the Files sidebar panel will show your connection with its detected protocol and root path.


## Using the panel

The storage inspector appears as a collapsible **Remote storage** section at the top of the **Files** sidebar panel.

| Action | How |
|--------|-----|
| **Browse** | Click a directory to expand it. Entries are fetched lazily. |
| **Search** | Type in the search box to filter loaded entries by name. Expand directories first to include their contents. |
| **Copy URL** | Right-click or use the `⋮` menu on any entry to copy its full URL (e.g., `s3://bucket/path/to/file.parquet`). |
| **Download** | Use the `⋮` menu on a file to download it through the marimo server. |
| **Refresh** | Click the refresh icon on a namespace header to re-fetch its entries. |

## Multiple connections

You can have multiple storage connections in the same notebook — each one appears as a separate namespace. The panel header shows the variable name so you can tell them apart.

```python
from obstore.store import S3Store

prod = S3Store.from_url("s3://prod-bucket")
staging = S3Store.from_url("s3://staging-bucket")
```
