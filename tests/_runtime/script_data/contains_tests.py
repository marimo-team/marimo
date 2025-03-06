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


# None of these should fail


@app.cell
def _():
    def inc(x):
        return x + 1

    return (inc,)


@app.cell
def _(inc, pytest):
    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5), (0, 1)])
    def test_parameterized(x, y):
        assert inc(x) == y, "These tests should pass."

    return (test_parameterized,)


@app.cell
def _(inc, pytest):
    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized_collected(x, y):
        assert inc(x) == y, "These tests should pass."

    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized_collected2(x, y):
        assert inc(x) == y, "These tests should pass."

    @pytest.mark.skip(reason="Skip for fun")
    def test_normal_regular():
        assert True

    class TestParent:
        def test_parent_inner(self):
            assert True

        class TestChild:
            def test_inner(self):
                assert True

    return (
        TestParent,
        test_normal_regular,
        test_parameterized_collected,
        test_parameterized_collected2,
    )


@app.cell
def _():
    def test_sanity():
        assert True


@app.cell
def imports():
    import pytest

    import marimo as mo

    return mo, pytest


if __name__ == "__main__":
    app.run()
