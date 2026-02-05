import marimo

__generated_with = "0.19.2"
app = marimo.App(layout_file="layouts/layout.json")


@app.cell
def _():
    x = 1
    return


if __name__ == "__main__":
    app.run()
