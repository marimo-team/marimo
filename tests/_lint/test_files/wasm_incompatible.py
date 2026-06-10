import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    import subprocess

    subprocess.run(["ls"])
    return


@app.cell
def _():
    import os

    os.system("echo hello")
    return


@app.cell
def _():
    breakpoint()
    return


@app.cell
def _():
    import pdb

    pdb.set_trace()
    return


@app.cell
def _():
    import multiprocessing

    return


@app.cell
def _():
    import pydecimal

    return


if __name__ == "__main__":
    app.run()
