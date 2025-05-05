import marimo

__generated_with = "0.11.25"
app = marimo.App(width="medium")


with app.setup:
    import pytest

    test_cases = [(1, 2), (1, 3), (1, 5)]


@app.cell
def _(test_cases):
    @pytest.mark.parametrize(("a", "b"), test_cases)
    def test_function(a, b):
        assert a < b

    return (test_function,)


@app.cell
def _():
    def inc(x):
        return x + 1

    return (inc,)


@app.cell
def collection_of_tests(inc, pytest):
    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_answer(x, y):
        assert inc(x) == y, "These tests should pass."


if __name__ == "__main__":
    app.run()
