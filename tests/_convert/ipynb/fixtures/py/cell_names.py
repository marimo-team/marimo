import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def my_imports():
    import os
    import sys
    return os, sys


@app.cell
def compute(os, sys):
    result = os.getcwd() + sys.platform
    return (result,)


@app.cell
def display(result):
    print(result)
    return


if __name__ == "__main__":
    app.run()
