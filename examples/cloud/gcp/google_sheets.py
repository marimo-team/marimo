import marimo

__generated_with = "0.1.43"
app = marimo.App(width="full")


@app.cell
def __():
    # Imports
    import marimo as mo
    import pandas as pd
    import os
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from oauth2client.client import GoogleCredentials
    return GoogleCredentials, ServiceAccountCredentials, gspread, mo, os, pd


@app.cell
def __(mo):
    mo.md(
        f"""
    # Google Sheets

    Required dependencies:
    ```sh
    $ pip install gspread
    ```
    """
    )
    return


@app.cell
def __(mo):
    # Configuration
    credentials = mo.ui.text(label="(Optional) Path to credentials file").form()
    mo.accordion(
        {
            "⚙️ Configuration": mo.md(
                f"""
                This app requires a Google Cloud Platform account and a bucket to access. You will need to be authenticated with `gcloud auth login`, 
                or provide a path to a credentials file.

                {credentials}
                 """
            )
        }
    )
    return credentials,


@app.cell
def __(
    GoogleCredentials,
    ServiceAccountCredentials,
    credentials,
    gspread,
    os,
):
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
    return creds, gc


@app.cell
def __(mo):
    spreadsheet_url = mo.ui.text_area(label="Spreadsheet URL").form()
    spreadsheet_url
    return spreadsheet_url,


@app.cell
def __(gc, mo, pd, spreadsheet_url):
    mo.stop(not spreadsheet_url.value)

    # Get sheet records
    wks = gc.open_by_url(spreadsheet_url.value).sheet1
    mo.ui.table(pd.DataFrame(wks.get_all_records()), selection=None)
    return wks,


if __name__ == "__main__":
    app.run()
