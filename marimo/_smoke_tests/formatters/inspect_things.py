import marimo

__generated_with = "0.16.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import functools
    return functools, mo, np


@app.cell
def _(mo):
    mo.inspect(mo, value=False)
    return


@app.cell
def _(mo, np):
    mo.inspect(np)
    return


@app.cell
def _():
    def fib(n):
        """Return the nth Fibonacci number"""
        if n <= 1:
            return n
        else:
            a, b = 0, 1
            for _ in range(n - 1):
                a, b = b, a + b
            return b


    fib
    return


@app.class_definition
class Foo:
    def __init__(self):
        pass

    def __str__():
        pass

    def bar():
        pass

    def _baz():
        pass


@app.cell
def _():
    Foo
    return


@app.cell
def _():
    Foo.__init__
    return


@app.cell
def _():
    Foo.__str__
    return


@app.cell
def _():
    Foo.bar
    return


@app.cell
def _():
    Foo().bar
    return


@app.cell
def _():
    Foo._baz
    return


@app.cell
def _(functools):
    @functools.cache
    def square(x):
        return x * x


    square
    return


@app.cell
def _():
    lambda_func = lambda x: x * 2
    lambda_func
    return


@app.cell
def _():
    # built in
    len
    return


if __name__ == "__main__":
    app.run()
