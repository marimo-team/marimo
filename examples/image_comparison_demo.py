#!/usr/bin/env python3
# Copyright 2024 Marimo. All rights reserved.

"""
Image comparison demo using Marimo's slider functionality
"""

import marimo

__generated_with = "0.11.25"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Image Comparison Demo

        This demo showcases the `mo.image_compare` feature, which allows for side-by-side comparison of images.

        ## Basic Usage - Horizontal Comparison

        The default orientation is horizontal, where you can slide left and right to compare images:
        """
    )
    return


@app.cell
def _():
    before_image_path = "before.jpg"
    after_image_path = "after.jpg"
    return after_image_path, before_image_path


@app.cell
def _(after_image_path, before_image_path, mo):
    # Basic horizontal comparison with default settings
    mo.image_compare(before_image=before_image_path, after_image=after_image_path)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Custom Labels

        You can add custom labels to each image:
        """
    )
    return


@app.cell
def _(after_image_path, before_image_path, mo):
    mo.image_compare(
        before_image=before_image_path,
        after_image=after_image_path,
        direction="horizontal",
        show_labels=True,
        before_label="Before",
        after_label="After",
        height=1000,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Vertical Comparison

        You can also use a vertical comparison slider:
        """
    )
    return


@app.cell
def _(after_image_path, before_image_path, mo):
    mo.image_compare(
        before_image=before_image_path,
        after_image=after_image_path,
        direction="vertical",
        show_labels=True,
        before_label="Before",
        after_label="After",
        height=400,
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
