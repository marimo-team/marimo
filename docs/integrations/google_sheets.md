# Google Sheets

## Getting Started

To use Google Sheets as a data source, you will need to install the `gspread` and `oauth2client` Python packages. You can install this package using `pip`:

```bash
pip install gspread oauth2client
```

## Authentication

### Application Default Credentials (Recommended)

The easiest way to authenticate with Google Sheets is to use [Application Default Credentials](https://cloud.google.com/docs/authentication/production). If you are running marimo on Google Cloud and your resource has a service account attached, then Application Default Credentials will automatically be used.
If you are running marimo locally, you can authenticate with Application Default Credentials by running the following command:

```bash
gcloud auth application-default login
```

### Service Account Key File

To authenticate with Google Sheets, you will need to create a service account and download the service account key file. You can create a service account and download the key file by following the instructions [here](https://cloud.google.com/iam/docs/creating-managing-service-account-keys).

Once you have downloaded the key file, you can authenticate with Google Sheets by setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of the key file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key/file.json
```

## Reading Data

To read data from Google Sheets, you will need to authenticate and create a `gspread.Client`. You can then use this object to read data from Google Sheets.

```python
# Cell 1 - Load libraries
import marimo as mo
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Authenticate with Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scope
)
gc = gspread.authorize(credentials)

# Cell 2 - Load the sheet
wks = gc.open("marimo").sheet1
mo.ui.table(pd.DataFrame(wks.get_all_records()))
```

## Example

Check out our full example using Google Sheets [here](https://github.com/marimo-team/marimo/blob/main/examples/cloud/gcp/google_sheets.py)

Or run it yourself:

```bash
marimo run https://raw.githubusercontent.com/marimo-team/marimo/main/examples/cloud/gcp/google_sheets.py
```
