import marimo

__generated_with = "0.11.2"
app = marimo.App(_toplevel_fn=True)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # @app.function smoke test

        See [2293 for discussion](https://github.com/marimo-team/marimo/issues/2293)[^2293]

        [^2293]: https://github.com/marimo-team/marimo/issues/2293
        """
    )
    return


@app.function
def self_ref_fib(n: int) -> int:
    if n == 0:
        return 0
    if n == 1:
        return 1
    return self_ref_fib(n - 1) + self_ref_fib(n - 2)


@app.function(disabled=True, hide_code=True)
def divide(x, y):
    return y / x


@app.function
def subtraction(a: "int", b: "int") -> "int":
    return a - b


@app.function
# Comments inbetween
def multiply(a, b) -> "int":
    return a * b


@app.function
def addition(a: int, b: int) -> int:
    # int is considered no good, re-eval
    return a + b


@app.cell
def bad_divide_curry(divide):
    # Has an external ref currently does not work
    def bad_divide_curry(x):
        # Filler line
        # To push the error
        return divide(0, x)
        # With lines below
    return (bad_divide_curry,)


@app.cell
def _(addition, multiply, self_ref_fib):
    # Should be be a regular cell
    print(addition(21, 56))
    print(multiply(21, 56))
    print(self_ref_fib(10))
    return


@app.cell
def _(bad_divide_curry):
    a = bad_divide_curry(1)
    return (a,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
