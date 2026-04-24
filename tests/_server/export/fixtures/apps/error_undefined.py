import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _(undefined_variable):
    x = undefined_variable  # noqa: F821
    return


if __name__ == "__main__":
    app.run()
