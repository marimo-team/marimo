import marimo

__generated_with = "0.11.1"
app = marimo.App()


@app.function(
    # Filler Lines
    # Filler Lines
)
def bad_divide(x, y):
    # Filler line
    # To push the error
    return y / x
    superfluous_expression = 1


# Also a check for no call
@app.function
# Technically legal, but messy
def bad_divide_curry(x):
    # Filler line
    # To push the error
    # Even further
    superfluous_expression = 1
    return bad_divide(0, x)
    # With lines below


@app.cell
def _(bad_divide_curry):  # TODO: Consider removing from signature?
    a = bad_divide_curry(1)
    return a


if __name__ == "__main__":
    app.run()
