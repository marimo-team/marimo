# Copyright 2026 Marimo. All rights reserved.
"""
Smoke test for setup cell embedding.

This tests the scenario where:
- Main app has a setup cell
- Inner app has a setup cell
- Main app embeds the inner app

Bug: The main app's setup cell should NOT rerun when the inner app is embedded.
"""

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")

with app.setup:
    setup_tracker = {"count": 0}
    setup_tracker["count"] += 1
    import marimo as mo
    from inner_with_setup import app as inner_app


@app.cell(hide_code=True)
def _():
    mo.md("""
    # Setup Cell Embedding Smoke Test

    This notebook tests embedding an app with a setup cell from a notebook
    that also has a setup cell
    The outer app's setup cell should only run **once**, not rerun when
    the inner app is embedded.
    """)
    return


@app.cell
def _():
    setup_count_before_embed = setup_tracker["count"]
    mo.md(f"Setup run count before embed: **{setup_count_before_embed}**")
    return (setup_count_before_embed,)


@app.cell
async def _():
    # Embed the inner app (which also has a setup cell)
    result = await inner_app.embed()
    result.output
    return (result,)


@app.cell
def _(result):
    mo.md(f"""
    Inner app value: **{result.defs.get('inner_value')}**
    """)
    return


@app.cell
def _(setup_count_before_embed):
    setup_count_after_embed = setup_tracker["count"]

    # This is the key assertion - setup should still be 1
    status = "PASS" if setup_count_after_embed == 1 else "FAIL"
    color = "green" if status == "PASS" else "red"

    mo.md(f"""
    ## Test Result: <span style="color: {color}">{status}</span>

    - Setup run count before embed: {setup_count_before_embed}
    - Setup run count after embed: {setup_count_after_embed}

    Expected setup to run exactly **1** time.
    """)
    return


if __name__ == "__main__":
    app.run()
