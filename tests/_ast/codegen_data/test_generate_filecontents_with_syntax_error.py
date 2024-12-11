import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one():
    import numpy as np
    return (np,)


app._unparsable_cell(
    r"""
    _ error
    """,
    name="two"
)


@app.cell
def __1f24():
    'all good'
    return


app._unparsable_cell(
    r"""
    _ another_error
    _ and \"\"\"another\"\"\"

        \t
    """,
    name="__1d37"
)


if __name__ == "__main__":
    app.run()
