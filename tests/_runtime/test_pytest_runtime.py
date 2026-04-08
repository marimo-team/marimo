from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from marimo._runtime.pytest import run_pytest as _run_pytest_type
    from tests._runtime.script_data.contains_tests import app as _app_type

# Format: (passed, skipped, failed, errors)
_DEF_COUNT = {
    # fixtures, not tests
    "function_fixture": (0, 0, 0, 0),
    "scoped_fixture": (0, 0, 0, 0),
    "isolated_fixture": (0, 0, 0, 0),
    # tests
    "TestParent": (2, 0, 0, 0),
    "test_failure": (0, 0, 1, 0),
    "test_parameterized": (3, 0, 0, 0),
    "test_parameterized_collected": (2, 0, 0, 0),
    "test_sanity": (1, 0, 0, 0),
    "test_skip": (0, 1, 0, 0),
    "test_using_var_in_scope": (3, 0, 0, 0),
    "test_using_var_in_toplevel": (3, 0, 0, 0),
    # Fixtures - these now work with fixture preservation
    "test_uses_scoped_fixture": (1, 0, 0, 0),
    "test_parametrize_with_scoped_fixture": (2, 0, 0, 0),
    "TestWithClassFixture": (1, 0, 0, 0),
    "TestClassDefinitionWithFixtures": (3, 0, 0, 0),
    "test_uses_top_level_fixture": (1, 0, 0, 0),
    "test_parametrize_with_toplevel_fixture": (2, 0, 0, 0),
    "test_uses_function_fixture": (1, 0, 0, 0),
    # Fixture dependency chain test
    "base_fixture": (0, 0, 0, 0),  # fixture, not a test
    "dependent_fixture": (0, 0, 0, 0),  # fixture, not a test
    "test_fixture_dependency_chain": (1, 0, 0, 0),
    # Null cases - fixture not in scope / doesn't exist (errors)
    "test_cross_cell_fixture_fails": (0, 0, 0, 1),
    "test_missing_fixture": (0, 0, 0, 1),
}

_ISOLATION_DEFS = {"test_cross_cell_fixture_fails", "test_missing_fixture"}


@pytest.fixture(scope="module")
def notebook_env() -> tuple[
    type[_app_type], dict[str, object], Path, type[_run_pytest_type]
]:
    from marimo._runtime.pytest import run_pytest
    from tests._runtime.script_data.contains_tests import app

    _, lcls = app.run()
    lcls = dict(lcls)
    path = Path(__file__).parent / "script_data/contains_tests.py"

    # Turn off for recursion guard
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ["PYTEST_CURRENT_TEST"] = ""
    del os.environ["PYTEST_CURRENT_TEST"]
    # Give time for env changes to sync (helps with race conditions on Windows)
    asyncio.run(asyncio.sleep(0.1))

    yield app, lcls, path, run_pytest

    if previous:
        os.environ["PYTEST_CURRENT_TEST"] = previous
    else:
        os.environ.pop("PYTEST_CURRENT_TEST", None)


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_batched_cells(notebook_env):
    """Batch all non-isolation cells into a single run_pytest call."""
    app, lcls, path, run_pytest = notebook_env

    batch_defs: set[str] = set()
    batch_expected = [0, 0, 0, 0]  # passed, skipped, failed, errors
    for cell in app._cell_manager.cells():
        if cell and cell.__test__ and not (cell.defs & _ISOLATION_DEFS):
            batch_defs.update(cell.defs)
            for d in cell.defs:
                for i, v in enumerate(_DEF_COUNT[d]):
                    batch_expected[i] += v

    response = run_pytest(defs=batch_defs, lcls=lcls, notebook_path=path)
    assert (
        response.passed,
        response.skipped,
        response.failed,
        response.errors,
    ) == tuple(batch_expected), response.output
    assert response.total == 28


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_isolation_cells(notebook_env):
    """Isolation tests run separately to verify fixture scoping errors."""
    app, lcls, path, run_pytest = notebook_env

    total = 0
    for cell in app._cell_manager.cells():
        if cell and cell.__test__ and (cell.defs & _ISOLATION_DEFS):
            response = run_pytest(
                defs=cell.defs, lcls=lcls, notebook_path=path
            )
            expected = tuple(
                map(sum, zip(*[_DEF_COUNT[d] for d in cell.defs]))
            )
            assert (
                response.passed,
                response.skipped,
                response.failed,
                response.errors,
            ) == expected, response.output
            total += response.total
    assert total == 2


def test_pytest_result_summary_includes_xfail() -> None:
    from marimo._runtime.pytest import MarimoPytestResult

    result = MarimoPytestResult(
        passed=2, failed=1, errors=0, skipped=1, xfailed=3, xpassed=1
    )
    assert result.total == 8
    assert "XFailed: 3" in result.summary
    assert "XPassed: 1" in result.summary


def test_pytest_result_summary_omits_zero_xfail() -> None:
    from marimo._runtime.pytest import MarimoPytestResult

    result = MarimoPytestResult(passed=5, failed=0, errors=0, skipped=0)
    assert "XFailed" not in result.summary
    assert "XPassed" not in result.summary
