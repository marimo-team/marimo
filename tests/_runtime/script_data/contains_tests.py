# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "marimo",
# ]
# ///
# Copyright 2025 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.10"
app = marimo.App()


with app.setup:
    import pytest

    test_cases = [(1, 2), (1, 3), (1, 5)]


@app.function
def inc(x):
    return x + 1


@app.function
@pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5), (0, 1)])
def test_parameterized(x, y):
    assert inc(x) == y, "These tests should pass."


@app.cell
def _(inc):
    @pytest.mark.parametrize(("x", "y"), [(3, 4), (4, 5)])
    def test_parameterized_collected(x, y):
        assert inc(x) == y, "These tests should pass."

    class TestParent:
        def test_parent_inner(self):
            assert True

        class TestChild:
            def test_inner(self):
                assert True

    return (
        TestParent,
        test_parameterized_collected,
    )


@app.cell
def _():
    def test_sanity():
        assert True

    def test_failure():
        pytest.fail("Ensure a failure is captured.")

    @pytest.mark.skip(reason="Ensure a skip is captured.")
    def test_skip():
        assert True


@app.cell
def _():
    @pytest.mark.parametrize(("a", "b"), test_cases)
    def test_using_var_in_scope(a, b):
        assert a < b


@app.function
@pytest.mark.parametrize(("a", "b"), test_cases)
def test_using_var_in_toplevel(a, b):
    assert a < b


if __name__ == "__main__":
    app.run()
