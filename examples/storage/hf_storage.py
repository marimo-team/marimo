# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "huggingface-hub==1.24.0",
#     "marimo>=0.23.15",
#     "polars==1.43.0",
# ]
# ///

# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Hugging Face Hub in Remote Storage (`HfApi`)

    Create an [`HfApi`](https://huggingface.co/docs/huggingface_hub/package_reference/hf_api) client
    and marimo will discover it in the **Remote Storage** panel. Browse your datasets,
    models, spaces, and buckets — then read files with `hf://` URLs in Polars or pandas.
    """)
    return


@app.cell
def _():
    from huggingface_hub import HfApi

    hf = HfApi()
    return (hf,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## List files in a dataset repo

    Expand **Hugging Face Hub** in Remote Storage, or list from code:
    """)
    return


@app.cell
def _(hf):
    list(
        hf.list_repo_tree(
            "scikit-learn/Fish",
            repo_type="dataset",
        )
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Read the file directly via `hf://`
    """)
    return


@app.cell
def _(pl):
    df = pl.read_csv("hf://datasets/scikit-learn/Fish/Fish.csv")
    df
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


if __name__ == "__main__":
    app.run()
