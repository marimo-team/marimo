import marimo

__generated_with = "0.16.3"
app = marimo.App()


@app.cell
def _():
    import pandas as pd  # Should trigger MR001 if pandas exists in site-packages
    return


@app.cell
def _():
    # Test that we can still define functions
    def my_function():
        return "pandas specific logic"
    return


if __name__ == "__main__":
    app.run()