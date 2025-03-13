

import marimo

__generated_with = "0.11.19"
app = marimo.App()

with app.setup:
    import marimo as mo


@app.cell(hide_code=True)
def _():
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
    """This is my doc string"""
    if n == 0:
        return 0
    if n == 1:
        return 1
    return self_ref_fib(n - 1) + self_ref_fib(n - 2)


@app.function(hide_code=True)
def divide(x, y):
    return y / x


@app.function
def subtraction(a: "int", b: "int") -> "int":
    """This is new doc string"""
    return a - b


@app.cell
def multiply(d):
    # Comments inbetween
    def multiply(a, b) -> int:
        return a * b + d
    return (multiply,)


@app.cell
def _():
    d = 13
    return (d,)


@app.function(hide_code=True)
def addition(a: int, b: int) -> int:
    # int is considered no good, re-eval.
    return a + b


@app.function
# Has an external ref currently does not work
def bad_divide_curry(x):
    # Filler line
    # To push the error
    return divide(0, x)
    # With lines below


@app.cell
def _(multiply):
    # Should be be a regular cell
    print(addition(21, 56))
    print(multiply(21, 56))
    print(self_ref_fib(10))
    return


@app.cell
def _():
    a = bad_divide_curry(1)
    return


if __name__ == "__main__":
    app.run()
