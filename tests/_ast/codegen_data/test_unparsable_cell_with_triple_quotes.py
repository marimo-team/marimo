import marimo

__generated_with = "0.0.0"
app = marimo.App()


@app.cell
def _():
    x = 1
    return


app._unparsable_cell(
    """
    \"\"\"
    ```python {.marimo}
    print(\"Hello, World!\")
    """,
    name="_"
)


app._unparsable_cell(
    r"""
    it's an unparsable cell
    """,
    name="_"
)


if __name__ == "__main__":
    app.run()
