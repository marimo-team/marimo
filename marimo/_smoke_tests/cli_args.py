# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    Re-run this with notebook with the following command line:

    ```bash
    marimo edit marimo/_smoke_tests/cli_args.py -- -a foo --b=bar -d 10 -d 20 -d false
    ```
    """)


@app.cell
def _(mo):
    mo.cli_args().to_dict()


if __name__ == "__main__":
    app.run()
