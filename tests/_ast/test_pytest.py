from __future__ import annotations

import pytest

import marimo

app = marimo.App()


@app.cell
def imports():
    import marimo as mo

    # Suffixed with _fixture should have corresponding definitions in conftest.py
    mo_fixture = None

    return mo, mo_fixture


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
