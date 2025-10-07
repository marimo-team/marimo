import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")


app._unparsable_cell(
    r"""
    This is a syntax error
    """,
    name="_"
)


@app.cell
def _():
    # This is a blank cell
    return


@app.cell
def _():
    a = 1
    return


app._unparsable_cell(
    r"""
    This is another syntax error
    """,
    name="_"
)


@app.cell
def _():
    a = 2
    return


app._unparsable_cell(
    r"""
    from math import *
    """,
    name="_"
)


@app.cell
def _():
    a = 3
    return


# Test multiple variables with multiple definitions
@app.cell
def _():
    b = 1
    c = 1
    return b, c


app._unparsable_cell(
    r"""
    x = 1 +
    """,
    name="_"
)


@app.cell
def _():
    b = 2
    c = 2
    return b, c


# Test with function definitions
@app.cell
def _():
    def foo():
        return 1
    return foo,


app._unparsable_cell(
    r"""
    def broken(
        x
    """,
    name="_"
)


@app.cell
def _():
    def foo():
        return 2
    return foo,


# Test with class definitions
@app.cell
def _():
    class Bar:
        pass
    return Bar,


app._unparsable_cell(
    r"""
    class Broken
        pass
    """,
    name="_"
)


@app.cell
def _():
    class Bar:
        pass
    return Bar,


# Test with import statements
@app.cell
def _():
    import os
    return os,


app._unparsable_cell(
    r"""
    import sys as
    """,
    name="_"
)


@app.cell
def _():
    import os
    return os,


# Test multiple definitions with cycles (referencing each other)
@app.cell
def _():
    d = e + 1
    return d,


app._unparsable_cell(
    r"""
    for i in
    """,
    name="_"
)


@app.cell
def _():
    e = d + 1
    return e,


if __name__ == "__main__":
    app.run()
