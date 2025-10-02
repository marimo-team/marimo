import marimo

__generated_with = "0.16.3"
app = marimo.App()


@app.cell
def _():
    import pandas as pd  # Should trigger MR001 - conflicts with pandas in site-packages
    return


@app.cell
def _():
    # Test a different import style
    from pandas import DataFrame
    return


if __name__ == "__main__":
    app.run()