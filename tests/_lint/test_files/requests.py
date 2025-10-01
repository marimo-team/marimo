import marimo

__generated_with = "0.16.3"
app = marimo.App()


@app.cell
def _():
    import requests  # Should trigger MR001 - file named requests.py importing requests
    return


@app.cell
def _():
    # Test different import style
    from requests import get
    return


if __name__ == "__main__":
    app.run()