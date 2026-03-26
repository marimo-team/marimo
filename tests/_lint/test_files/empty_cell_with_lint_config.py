# /// script
# [tool.marimo.lint]
# ignore = ["MF004"]
# ///
import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    return


@app.cell
def normal_cell():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
