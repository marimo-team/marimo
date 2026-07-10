import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import sys
    import platform
    import os

    return mo, os, platform, sys


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Hello, from inside Modal!
    """)
    return


@app.cell
def _(mo):
    import subprocess

    try:
        result = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        output = mo.md(
            f"""## 🚀 GPU is available:
    ```
    {result.stdout.decode()}

    ```
        """,
        )
    except FileNotFoundError:
        output = mo.md("## ✅️ We are running on CPU")

    output
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Runtime information
    """)
    return


@app.cell
def _(mo, os, platform, sys):
    runtime_info = {
        "python_version": sys.version,
        "platform": sys.platform,
        "arch": platform.machine(),
        "executable_path": sys.executable,
        "implementation": sys.implementation.name,
        "sys.path": sys.path,
        "argv": sys.argv,
        "working_directory": os.getcwd(),
        "ls": os.listdir(os.getcwd()),
    }
    mo.ui.table(runtime_info, selection=None, page_size=len(runtime_info))
    return


if __name__ == "__main__":
    app.run()
