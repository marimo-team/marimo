import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
def _():
    import subprocess

    subprocess.Popen(["sleep", "1000"])
    return


@app.cell
def _():
    import os

    os.system('ps -ef | grep sleep')
    return


if __name__ == "__main__":
    app.run()
