from __future__ import annotations

import pytest

import marimo

app = marimo.App()


@app.cell
async def _(pytest, x, y, Z):
    @pytest.mark.xfail(
        reason=("To ensure this doesn't just eval."),
        raises=AssertionError,
        strict=True,
    )
    def test_independence():
        assert x + y == 0

    def test_another_dependent_cell():
        assert x + y == Z

    class TestClass:
        @pytest.mark.xfail(
            reason=("To ensure this doesn't just eval."),
            raises=AssertionError,
            strict=True,
        )
        def test_method(self):
            assert x + y == 0

        @staticmethod
        @pytest.mark.xfail(
            reason=("To ensure this doesn't just eval."),
            raises=AssertionError,
            strict=True,
        )
        def test_static_method() -> None:
            assert x + y == 0

        def test_normal(self):
            assert x + y == Z

        @staticmethod
        def test_static() -> None:
            assert x + y == Z

    async def test_async_cell():
        assert True


@app.cell
def imports():
    import marimo as mo

    # Suffixed with _fixture should have corresponding definitions in conftest.py
    mo_fixture = None

    import pytest

    return mo, mo_fixture, pytest


@app.cell
def test_cell_is_invoked():
    assert True


@app.cell
async def test_async_cell():
    assert True


@app.function
def test_top_level_function():
    assert True


@pytest.mark.xfail(
    reason=("To ensure this doesn't just eval as a cell defining a function."),
    raises=AssertionError,
    strict=True,
)
@app.function
def test_top_level_function_fails():
    raise AssertionError("Function called")


@app.cell
def test_cell_has_builtin_refs():
    assert len([print, sum, list]) == 3


@pytest.mark.xfail(
    reason=("Ensure correct errors are propagated through a failing cell."),
    raises=ZeroDivisionError,
    strict=True,
)
@app.cell
def test_cell_fails_correctly():
    z = 1 / 0
    return z


@app.cell
def test_cell_deps_work(mo):
    assert mo.app_meta().mode == "test"


@app.cell
def test_cell_fixtures_work(mo_fixture):
    assert mo_fixture.app_meta().mode == "test"


@pytest.mark.xfail(
    reason="Function actually expects 1 argument, but 0 are provided.",
    raises=TypeError,
    strict=True,
)
@app.cell
def test_cell_missing_refs_fail():
    assert mo.app_meta().mode == "test"  # noqa: F821


@pytest.mark.xfail(
    reason="Function actually expects 0 argument, but 1 is provided.",
    raises=TypeError,
    strict=True,
)
@app.cell
def test_cell_extra_refs_fail(mo):  # noqa: ARG001
    assert True


@pytest.mark.xfail(
    reason="Provided argument is not the expected argument.",
    raises=TypeError,
    strict=True,
)
@app.cell
def test_cell_args_resolved_by_name(mo):  # noqa: ARG001
    assert x  # noqa: F821


@app.cell
def test_cell_assert_rewritten(pytest):
    a = 1
    b = 2

    with pytest.raises(AssertionError) as exc_info:
        assert a + b == a * b

    # Check expansion works. Without rewrite, this just produces
    # "AssertionError", without showing the expanded expression.
    assert "assert (1 + 2) == (1 * 2)" in str(exc_info.value)


@app.cell
def cell_with_multiple_deps():
    x = 1
    y = 2
    Z = 3
    return x, y, Z
