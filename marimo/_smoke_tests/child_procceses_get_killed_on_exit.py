# /// script
# dependencies = ["marimo"]
# requires-python = ">=3.13"
# ///

import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
def _():
    import subprocess

    # When you shut down this notebook, the sleep command should also be
    # killed.
    proc = subprocess.Popen(["sleep", "100"])
    print(f"Started subprocess with PID: {proc.pid}")
    return


@app.cell
def _():
    import os

    os.system('ps -ef | grep sleep')
    return


if __name__ == "__main__":
    app.run()
