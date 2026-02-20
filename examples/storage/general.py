# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fsspec==2026.2.0",
#     "marimo>=0.19.9",
#     "obstore==0.8.2",
#     "python-dotenv==1.2.1",
#     "requests==2.32.5",
#     "s3fs==2026.2.0",
# ]
# ///

import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from fsspec.implementations.local import LocalFileSystem
    from fsspec.implementations.github import GithubFileSystem
    import s3fs
    import obstore
    import os
    from dotenv import load_dotenv

    load_dotenv()
    return GithubFileSystem, LocalFileSystem, os


@app.cell
def _(LocalFileSystem):
    local = LocalFileSystem(asynchronous=True)
    return


@app.cell
def _(os):
    from obstore.store import S3Store

    access_key_id = os.environ.get("CLOUDFLARE_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("CLOUDFLARE_SECRET_ACCESS_KEY")
    url = os.environ.get("CLOUDFLARE_MARIMO_URL")
    store = S3Store.from_url(
        f"{url}/marimo-artifacts",
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )
    return


@app.cell
def _(GithubFileSystem):
    marimo_repo = GithubFileSystem(org="marimo-team", repo="marimo")
    return (marimo_repo,)


@app.cell
def _(marimo_repo):
    print(marimo_repo.read_text("github://AGENTS.md"))
    return


@app.cell
def _():
    # s3_client = s3fs.S3FileSystem(
    #     endpoint_url=url,
    #     key=os.getenv("CLOUDFLARE_ACCESS_KEY_ID"),
    #     secret=os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY"),
    # )
    return


if __name__ == "__main__":
    app.run()
