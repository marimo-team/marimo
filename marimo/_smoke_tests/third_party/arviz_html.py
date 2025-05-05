

import marimo

__generated_with = "0.12.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import arviz as az

    centered_data = az.load_arviz_data("centered_eight")
    centered_data
    return


if __name__ == "__main__":
    app.run()
