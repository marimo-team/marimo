# Note that marimo is not repeated in the imports.

import marimo

__generated_with = "0.0.0"
app = marimo.App()

with app.setup:
    # Special setup cell
    import pytest


@app.function
# Sanity check that base case works.
def add(a, b):
    return a + b


@app.function
@pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 2), (1, 2, 3)])
def test_add_good(a, b, c):
    assert add(a, b) == c


@app.function
@pytest.mark.xfail(
    reason=("Check test is actually called."),
    raises=AssertionError,
    strict=True,
)
@pytest.mark.parametrize(("a", "b", "c"), [(1, 1, 3), (2, 2, 5)])
def test_add_bad(a, b, c):
    assert add(a, b) == c


if __name__ == "__main__":
    app.run()
