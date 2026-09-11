# /// script
# dependencies = ["marimo"]
# requires-python = ">=3.14"
# ///

import marimo

__generated_with = "0.24.1"
app = marimo.App(width="medium")


@app.cell
def _() -> None:
    return


@app.cell
def _() -> None:
    raise ValueError("ooops")
    return


@app.cell
def _() -> None:
    return


if __name__ == "__main__":
    app.run()
