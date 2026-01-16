import marimo

app = marimo.App()

app._unparsable_cell(
    r"""
    return
    """,
    name="__",
)

app._unparsable_cell(
    r"""
    partial_statement =
    """,
    name="__",
)


@app.cell
def __():
    valid_statement = 1
    return (valid_statement,)


if __name__ == "__main__":
    app.run()
