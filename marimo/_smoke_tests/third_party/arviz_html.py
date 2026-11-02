import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo


@app.cell
def _():
    import arviz as az

    centered_data = az.load_arviz_data("centered_eight")
    centered_data


if __name__ == "__main__":
    app.run()
