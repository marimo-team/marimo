#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Image Comparison Demo

    This demo showcases the `mo.image_compare` feature, which allows for side-by-side comparison of images.

    ## Basic Usage - Horizontal Comparison

    The default orientation is horizontal, where you can slide left and right to compare images:
    """)
    return


@app.cell
def _():
    before_image_path = "https://picsum.photos/200/301.jpg"
    after_image_path = "https://picsum.photos/200/300.jpg"
    return after_image_path, before_image_path


@app.cell
def _(after_image_path, before_image_path, mo):
    # Basic horizontal comparison with default settings
    mo.image_compare(before_image=before_image_path, after_image=after_image_path)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Custom Initial Position

    You can set the initial position of the slider:
    """)
    return


@app.cell
def _(after_image_path, before_image_path, mo):
    mo.image_compare(
        before_image=before_image_path,
        after_image=after_image_path,
        direction="horizontal",
        value=20,  # Start at 25% position
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Vertical Comparison

    You can also use a vertical comparison slider:
    """)
    return


@app.cell
def _(after_image_path, before_image_path, mo):
    mo.image_compare(
        before_image=before_image_path,
        after_image=after_image_path,
        direction="vertical",
        value=75,  # Start at 75% position
        height=400,
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
