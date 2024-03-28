import marimo

__generated_with = "0.3.4"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(
        """
    # Query params

    Open this URL [/?foo=1&bar=2&bar=3&baz=4](/?foo=1&bar=2&bar=3&baz=4)
    """
    )
    return


@app.cell
def __(mo):
    query_params = mo.query_params()
    return query_params,


@app.cell
def __(query_params):
    # change the value of a query param, and watch the next cell run automatically
    query_params["foo"] = 8
    return


@app.cell
def __(query_params):
    query_params
    return


@app.cell
def __():
    # mo.query_params()["abasdc"] = 11123123123
    return


@app.cell
def __():
    # mo.query_params().append("abc", 12)
    return


if __name__ == "__main__":
    app.run()
