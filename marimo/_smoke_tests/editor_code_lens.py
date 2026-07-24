# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars",
#     "duckdb",
#     "fsspec",
# ]
# ///

import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""
    # Editor code lens

    Requires the `editor_code_lens` experimental flag (on by default in dev
    builds; otherwise run `setFeatureFlag("editor_code_lens", true)` in the
    browser console). Cache icons also require the `cache_panel` flag.

    Each cell below creates something that gets a small inline icon next to
    it in the editor. Clicking the icon opens the matching panel:

    - dataframe or SQL engine → variables panel, data sources section
    - fsspec/obstore bucket → files panel, remote storage section
    - `mo.cache` / `mo.persistent_cache` → cache panel
    """)
    return


@app.cell
def _():
    import duckdb
    import fsspec
    import polars as pl

    import marimo as mo

    return duckdb, fsspec, mo, pl


@app.cell
def _(pl):
    # Dataframe: icon after `df`
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    return


@app.cell
def _(duckdb):
    # SQL engine: icon after `engine`
    engine = duckdb.connect()
    return


@app.cell
def _(fsspec):
    # Storage bucket: icon after `bucket`
    bucket = fsspec.filesystem("memory")
    bucket.pipe_file("smoke-test/hello.txt", b"hello from the code lens")
    return


@app.cell
def _(mo):
    # Cache: icons after `mo.cache` and `mo.persistent_cache`
    @mo.cache()
    def add(a: int, b: int) -> int:
        return a + b

    with mo.persistent_cache("editor_code_lens_smoke_test"):
        total = add(1, 2)
    total
    return


if __name__ == "__main__":
    app.run()
