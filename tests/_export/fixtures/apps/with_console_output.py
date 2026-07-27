import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import sys

    sys.stdout.write("hello stdout")
    return (sys,)


@app.cell
def _(sys):
    sys.stderr.write("hello stderr")
    return


if __name__ == "__main__":
    app.run()
