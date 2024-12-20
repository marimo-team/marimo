from __future__ import annotations

import pytest

import marimo

app = marimo.App()


@app.cell
def imports():
    # These have corresponding fixtures in conftest.py
    import marimo as mo_lib

    return mo_lib


@app.cell
def test_cell_is_invoked():
    assert True


@app.cell
async def test_async_cell():
    assert True


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
def test_cell_fixtures_work(mo_lib):
    assert mo_lib.app_meta().mode == "test"


@pytest.mark.xfail(
    reason="Function actually expects 1 argument, but 0 are provided.",
    raises=TypeError,
    strict=True,
)
@app.cell
def test_cell_missing_refs_fail():
    assert mo_lib.app_meta().mode == "test"  # noqa: F821


@pytest.mark.xfail(
    reason="Function actually expects 0 argument, but 1 is provided.",
    raises=TypeError,
    strict=True,
)
@app.cell
def test_cell_extra_refs_fail(mo_lib):  # noqa: ARG001
    assert True
