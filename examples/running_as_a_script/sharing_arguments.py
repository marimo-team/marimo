import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import argparse

    return (argparse,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    This notebook shows how to parametrize a notebook with optional command-line arguments.

    Run the notebook with

    ```bash
    marimo edit sharing_arguments.py
    ```

    or

    ```bash
    marimo edit sharing_arguments.py -- -learning_rate=1e-3
    ```

    (Note the `--` separating the filename from the arguments.)

    or

    ```bash
    python sharing_arguments.py -learning_rate=1e-3
    ```

    See help for the notebook's arguments with

    ```python
    python sharing_arguments.py --help
    ```
    """)
    return


@app.cell
def _(mo):
    default = mo.ui.number(1000, step=100)
    default
    return (default,)


@app.cell
def _(argparse, default):
    parser = argparse.ArgumentParser()

    parser.add_argument("-iterations", default=default.value)
    args = parser.parse_args()
    print(args.iterations)
    return


if __name__ == "__main__":
    app.run()
