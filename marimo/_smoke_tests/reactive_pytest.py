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


@app.cell
def _():
    def inc(x):
        return x + 1
    return (inc,)


@app.cell
def test_answer(inc):
    assert inc(3) == 5, "This test fails"
    return


@app.cell
def test_sanity(inc):
    assert inc(3) == 4, "This test passes"
    return


@app.cell
def _(inc, pytest):
    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized(x, y):
        assert inc(x) == y, "These tests should pass."
    return (test_parameterized,)


@app.cell
def _():
    def cross_cell_fail():
        assert False
    return (cross_cell_fail,)


@app.cell
def _(cross_cell_fail, inc, pytest):
    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized_collected(x, y):
        assert inc(x) == y, "These tests should pass."

    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized_collected2(x, y):
        assert inc(x) == y, "These tests should pass."

    @pytest.mark.skip(reason="Skip for fun")
    def test_normal_regular():
        assert True

    def test_transitive_uri():
        cross_cell_fail()


    class TestParent():
        def test_parent_inner(self):
            assert True
        class TestChild():
            def test_inner(self):
                assert True
    return (
        TestParent,
        test_normal_regular,
        test_parameterized_collected,
        test_parameterized_collected2,
        test_transitive_uri,
    )


@app.cell
def _():
    def test_sanity():
        assert True

    def test_orwell():
        a = 2
        b = 5
        assert a + a == b
    return test_orwell, test_sanity


@app.cell
def imports():
    import pytest
    import marimo as mo
    return mo, pytest


if __name__ == "__main__":
    app.run()
