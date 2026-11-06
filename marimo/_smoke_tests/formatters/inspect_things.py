import marimo

__generated_with = "0.25.2"
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


@app.cell
def _(mo, np):
    mo.inspect(np)


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


@app.cell
def _():
    Foo.__init__


@app.cell
def _():
    Foo.__str__


@app.cell
def _():
    Foo.bar


@app.cell
def _():
    Foo().bar


@app.cell
def _():
    Foo._baz


@app.cell
def _(functools):
    @functools.cache
    def square(x):
        return x * x


    square


@app.cell
def _():
    lambda_func = lambda x: x * 2
    lambda_func


@app.cell
def _():
    # built in
    len


if __name__ == "__main__":
    app.run()
