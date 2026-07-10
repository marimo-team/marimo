# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "gspread==6.1.2",
#     "marimo",
#     "oauth2client==4.1.3",
#     "pandas==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import os
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from oauth2client.client import GoogleCredentials

    return GoogleCredentials, ServiceAccountCredentials, gspread, mo, os, pd


@app.cell
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


@app.cell
def _(GoogleCredentials, ServiceAccountCredentials, credentials, gspread, os):
    # Set up client
    _scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if credentials.value:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials.value
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            credentials.value,
            _scopes,
        )
    else:
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        creds = GoogleCredentials.get_application_default().create_scoped(_scopes)

    gc = gspread.authorize(creds)
    return (gc,)


@app.cell
def _(mo):
    spreadsheet_url = mo.ui.text(label="Spreadsheet URL", full_width=True)
    spreadsheet_url
    return (spreadsheet_url,)


@app.cell
def _(gc, mo, pd, spreadsheet_url):
    mo.stop(not spreadsheet_url.value)

    # Get sheet records
    wks = gc.open_by_url(spreadsheet_url.value).sheet1
    mo.ui.table(pd.DataFrame(wks.get_all_records()), selection=None)
    return


if __name__ == "__main__":
    app.run()
