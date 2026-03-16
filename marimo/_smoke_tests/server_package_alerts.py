# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.20.4",
# ]
# ///

# Copyright 2026 Marimo. All rights reserved.
"""Smoke test for server-side package alerts (PR #8619).

Tests that missing-package alerts for server-side tools (ruff, nbformat)
correctly show the Install button and fire at most once per save.

SETUP:
  pip uninstall ruff nbformat -y

SCENARIOS:
  1. Format alert  - press Shift+Enter (format) → expect "Missing packages: ruff" banner with Install
  2. IPYNB alert   - enable auto-export IPYNB, save (Ctrl+S) → expect "Missing packages: nbformat" banner
  3. Once per save - save again immediately → banner should NOT appear a second time

TEARDOWN:
  pip install ruff nbformat
"""

import marimo

__generated_with = "0.20.4"
app = marimo.App(auto_download=["ipynb"])


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import matplotlib.pyplot as plt

    return


@app.cell
def _(mo):
    mo.md("""
    # Server Package Alert Smoke Test

    ## What to verify

    ### Scenario 1 — ruff missing alert
    1. Uninstall ruff: run `pip uninstall ruff -y` in your shell
    2. Click **Format** (Shift+Enter) on this cell
    3. ✅ Expect: red "Missing packages" banner appears with **ruff** listed and an **Install** button
    4. ✅ The Install button should always appear (regardless of whether you're in a venv)

    ### Scenario 2 — nbformat missing, alert appears automatically
    1. Uninstall nbformat: run `pip uninstall nbformat -y` in your shell
    2. Wait up to 5 seconds (auto-export runs on a 5-second interval)
    3. ✅ Expect: "Missing packages: nbformat" banner with Install button appears

    ### Scenario 3 — install into server env
    1. From the nbformat alert banner, click **Install**
    2. ✅ Expect: nbformat installs into the *server* Python environment
    3. Save again (Ctrl+S)
    4. ✅ Expect: auto-export to `.marimo/server_package_alerts.ipynb` succeeds (no more banner)

    ### Scenario 4 — sandbox mode
    ```
    marimo edit --sandbox marimo/_smoke_tests/server_package_alerts.py
    ```
    1. Uninstall nbformat inside the sandbox: `uv pip uninstall nbformat`
    2. Save → ✅ Expect: nbformat banner with Install button appears
    3. Click Install → ✅ Expect: installs into the sandbox env successfully
    """)
    return


@app.cell
def _(mo):
    # A cell with code to format — press Shift+Enter to trigger the ruff alert
    x = 1 + 1
    y = x * 2
    mo.md(f"Result: {y}")
    return


if __name__ == "__main__":
    app.run()
