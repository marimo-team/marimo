import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.raw_cli_args()
    return (mo,)


@app.cell
def _(mo):
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--arg", nargs=3, type=int)
    p.add_argument("-v", action="count")
    print(p.parse_args(mo.raw_cli_args()))
    return argparse, p


if __name__ == "__main__":
    app.run()
