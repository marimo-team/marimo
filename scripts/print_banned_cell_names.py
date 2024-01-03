import marimo

__generated_with = "0.1.69"
app = marimo.App()


@app.cell
def __():
    def format_keywords(l: list[str]):
        print('\n'.join(l))
    return format_keywords,


@app.cell
def __():
    RESERVED_BY_MARIMO = [
        # We reserve tokens starting with two underscores for
        # the future
        "__*",
        # We import marimo in the notebook file
        "marimo",
        # The notebook/app object
        "app"
    ]
    return RESERVED_BY_MARIMO,


@app.cell
def __(keyword):
    RESERVED_BY_PYTHON = keyword.softkwlist + keyword.kwlist
    return RESERVED_BY_PYTHON,


@app.cell
def __(RESERVED_BY_MARIMO, RESERVED_BY_PYTHON, format_keywords):
    print(format_keywords(RESERVED_BY_MARIMO + RESERVED_BY_PYTHON))
    return


@app.cell
def __():
    import keyword
    return keyword,


if __name__ == "__main__":
    app.run()
