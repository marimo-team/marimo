# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("""
    Re-run this with notebook with the following command line:

    ```bash
    marimo edit marimo/_smoke_tests/cli_args.py -- -a foo --b=bar -d 10 -d 20 -d false
    ```
    """)
    return


@app.cell
def __(mo):
    mo.cli_args().to_dict()
    return


if __name__ == "__main__":
    app.run()
