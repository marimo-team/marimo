import marimo

__generated_with = "0.12.0"
app = marimo.App(width="medium")


@app.cell
def _(os):
    os.environ["FOO_BAR_SECRET"]
    return


@app.cell
def _():
    import os
    return (os,)


if __name__ == "__main__":
    app.run()
