import marimo

__generated_with = "0.10.12"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    with open(mo.notebook_dir() / ".." / ".." / "pyproject.toml") as f:
        contents = f.read()

    mo.plain_text(contents)
    return contents, f


if __name__ == "__main__":
    app.run()
