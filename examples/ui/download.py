# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(json, mo, pd):
    # Text file download
    text_download = mo.download(
        data="Hello, world!".encode("utf-8"),
        filename="hello.txt",
        mimetype="text/plain",
        label="Download text",
    )

    # CSV download using pandas
    df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"], "age": [25, 30, 35]})
    csv_download = mo.download(
        data=df.to_csv().encode("utf-8"),
        filename="data.csv",
        mimetype="text/csv",
        label="Download CSV",
    )

    # JSON download
    data = {"message": "Hello", "count": 42}
    json_download = mo.download(
        data=json.dumps(data).encode("utf-8"),
        filename="data.json",
        mimetype="application/json",
        label="Download JSON",
    )

    mo.hstack([text_download, csv_download, json_download])
    return


@app.cell(hide_code=True)
def _(json, mo, pd):
    import time
    import asyncio


    # Text file download with lazy loading
    def get_text_data():
        time.sleep(1)
        return "Hello, world!".encode("utf-8")


    text_download_lazy = mo.download(
        data=get_text_data,
        filename="hello.txt",
        mimetype="text/plain",
        label="Download text",
    )


    # CSV download using pandas with lazy loading
    async def get_csv_data():
        await asyncio.sleep(1)
        _df = pd.DataFrame(
            {"name": ["Alice", "Bob", "Charlie"], "age": [25, 30, 35]}
        )
        return _df


    csv_download_lazy = mo.download(
        data=get_csv_data,
        filename="data.csv",
        mimetype="text/csv",
        label="Download CSV",
    )


    # JSON download with lazy loading
    async def get_json_data():
        await asyncio.sleep(1)
        _data = {"message": "Hello", "count": 42}
        return json.dumps(_data).encode("utf-8")


    json_download_lazy = mo.download(
        data=get_json_data,
        filename="data.json",
        mimetype="application/json",
        label="Download JSON",
    )


    mo.hstack([text_download_lazy, csv_download_lazy, json_download_lazy])
    return


@app.cell
def _():
    import pandas as pd
    import json

    return json, pd


if __name__ == "__main__":
    app.run()
