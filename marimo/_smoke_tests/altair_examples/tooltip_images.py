# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "altair",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    # Altair Tooltip Images

    This smoke test verifies that images in Altair tooltips render correctly
    and that the tooltip handler properly sanitizes potentially malicious content.

    **Tests:**
    1. External image URLs in tooltips
    2. Base64-encoded images in tooltips
    3. XSS vulnerability prevention
    """
    )
    return


@app.cell
def _():
    import altair as alt
    import pandas as pd

    # Create sample data with image URLs
    source = pd.DataFrame(
        {
            "a": [1, 2],
            "b": [1, 2],
            "image": [
                "https://marimo.io/logo.png",
                "https://marimo.io/favicon.ico",
            ],
        }
    )

    # Create chart with image tooltip
    chart = (
        alt.Chart(source)
        .mark_circle(size=200)
        .encode(
            x=alt.X("a", scale=alt.Scale(domain=[0, 3])),
            y=alt.Y("b", scale=alt.Scale(domain=[0, 3])),
            tooltip=["image"],
        )
        .properties(
            title="Scatter Plot with Image Tooltips - Hover to see images",
            width=400,
            height=400,
        )
    )

    chart
    return alt, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Instructions

    Hover over the circles to see the image tooltips.
    The images should render in the tooltip, not just show URLs as text.
    """
    )
    return


@app.cell
def _(alt, pd):
    # Example with base64 encoded image
    base64_image = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMjUiIGN5PSIyNSIgcj0iMjAiIGZpbGw9InJlZCIvPjwvc3ZnPg=="

    source2 = pd.DataFrame(
        {
            "x": [1, 2, 3],
            "y": [1, 2, 1],
            "name": ["Red Circle", "Blue Square", "Green Triangle"],
            "image": [
                base64_image,
                "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3QgeD0iMTAiIHk9IjEwIiB3aWR0aD0iMzAiIGhlaWdodD0iMzAiIGZpbGw9ImJsdWUiLz48L3N2Zz4=",
                "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBvbHlnb24gcG9pbnRzPSIyNSw1IDQwLDQwIDEwLDQwIiBmaWxsPSJncmVlbiIvPjwvc3ZnPg==",
            ],
        }
    )

    chart2 = (
        alt.Chart(source2)
        .mark_point(size=300, filled=True)
        .encode(
            x=alt.X("x", scale=alt.Scale(domain=[0, 4])),
            y=alt.Y("y", scale=alt.Scale(domain=[0, 3])),
            tooltip=["name", "image"],
        )
        .properties(
            title="Chart with Base64 Encoded Image Tooltips",
            width=400,
            height=300,
        )
    )

    chart2
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## XSS Security Tests

    These tests verify that the tooltip handler properly sanitizes
    potentially malicious content and prevents XSS attacks.

    **Expected behavior:** All XSS attempts should be neutralized.
    No alert boxes or script execution should occur when hovering.
    """
    )
    return


@app.cell
def _(alt, pd):
    # Test various XSS attack vectors
    xss_test_data = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 1, 2, 3, 4],
            "y": [1, 1, 1, 1, 2, 2, 2, 2],
            "label": [
                "Script Tag",
                "Event Handler",
                "JS URL",
                "IMG onerror",
                "SVG Script",
                "HTML Injection",
                "OnMouseOver",
                "Data URL JS",
            ],
            "image": [
                # Script tag injection
                '<script>alert("XSS")</script>',
                # Event handler
                "<img src=x onerror=\"alert('XSS')\">",
                # JavaScript URL
                "<a href=\"javascript:alert('XSS')\">click</a>",
                # IMG with onerror
                '<img src="invalid" onerror="alert(\'XSS\')">',
                # SVG with embedded script
                '<svg><script>alert("XSS")</script></svg>',
                # HTML injection
                "<div onclick=\"alert('XSS')\">Click me</div>",
                # OnMouseOver
                "<span onmouseover=\"alert('XSS')\">hover</span>",
                # Data URL with JavaScript
                "<img src=\"data:text/html,<script>alert('XSS')</script>\">",
            ],
        }
    )

    xss_chart = (
        alt.Chart(xss_test_data)
        .mark_circle(size=150)
        .encode(
            x=alt.X("x:O", title="Test Vector"),
            y=alt.Y("y:O", title="Category"),
            color=alt.Color(
                "label:N",
                legend=alt.Legend(title="Attack Type"),
            ),
            tooltip=["label", "image"],
        )
        .properties(
            title="XSS Security Test - Hover to verify sanitization",
            width=600,
            height=300,
        )
    )

    xss_chart
    return


if __name__ == "__main__":
    app.run()
