# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.function
def inc(x):
    """Increment x by 1."""
    return x + 1


@app.cell
def test_answer():
    """Assert that inc(3) equals 5 (this test is expected to fail)."""
    assert inc(3) == 5, "This test fails"
    return


@app.cell
def test_sanity():
    """Assert that inc(3) equals 4 (this test should pass)."""
    assert inc(3) == 4, "This test passes"
    return


@app.cell
def _(pytest):
    @pytest.mark.parametrize("x, y", [(3, 4), (4, 5)])
    def test_parameterized(x, y):
        assert inc(x) == y, "These tests should pass."
    return


@app.function
def cross_cell_fail():
    """Unconditionally raise an AssertionError."""
    assert False


@app.cell
def _(pytest):
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
    return


@app.cell
def _():
    def test_sanity():
        assert True

    def test_orwell():
        a = 2
        b = 5
        assert a + a == b
    return


@app.cell
def imports():
    """Import pytest and marimo for use in test cells."""
    import pytest
    import marimo as mo
    return (pytest,)


if __name__ == "__main__":
    app.run()
