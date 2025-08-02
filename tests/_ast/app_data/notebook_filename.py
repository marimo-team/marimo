import marimo

__generated_with = "0.14.15"
app = marimo.App(width="medium")


with app.setup:
    import marimo as mo


@app.cell
def _():
    this_is_foo_path = mo.notebook_dir()
    this_is_foo_path
    return


@app.cell
def _():
    this_is_foo_file = __file__
    this_is_foo_file
    return


if __name__ == "__main__":
    app.run()
