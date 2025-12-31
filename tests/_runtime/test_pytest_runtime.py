import os
from pathlib import Path

from marimo._runtime.pytest import run_pytest

pytest_plugins = ["pytester"]


def test_smoke_test():
    from tests._runtime.script_data.contains_tests import app

    _, lcls = app.run()
    lcls = dict(lcls)

    def_count = {
        # fixtures, not tests
        "function_fixture": (0, 0, 0),
        "scoped_fixture": (0, 0, 0),
        # tests
        "TestParent": (2, 0, 0),
        "test_failure": (0, 0, 1),
        "test_parameterized": (3, 0, 0),
        "test_parameterized_collected": (2, 0, 0),
        "test_sanity": (1, 0, 0),
        "test_skip": (0, 1, 0),
        "test_using_var_in_scope": (3, 0, 0),
        "test_using_var_in_toplevel": (3, 0, 0),
        # Fixtures - these now work with fixture preservation
        "test_uses_scoped_fixture": (1, 0, 0),
        "test_parametrize_with_scoped_fixture": (
            2,
            0,
            0,
        ),  # parametrize + fixture
        "TestWithClassFixture": (1, 0, 0),
        "TestClassDefinitionWithFixtures": (3, 0, 0),
        "test_uses_top_level_fixture": (1, 0, 0),
        "test_parametrize_with_toplevel_fixture": (
            2,
            0,
            0,
        ),  # parametrize + fixture
        "test_uses_function_fixture": (1, 0, 0),
    }

    path = Path(__file__).parent / "script_data/contains_tests.py"

    # Turn off for recursion guard
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ["PYTEST_CURRENT_TEST"] = ""
    del os.environ["PYTEST_CURRENT_TEST"]

    # sanity check for run
    total = 0
    for cell in app._cell_manager.cells():
        if cell.__test__:
            response = run_pytest(
                defs=cell.defs, lcls=lcls, notebook_path=path
            )
            assert (
                response.passed,
                response.skipped,
                response.failed,
            ) == tuple(map(sum, zip(*[def_count[d] for d in cell.defs]))), (
                response.output
            )
            total += response.total

    os.environ["PYTEST_CURRENT_TEST"] = previous
    # put it back on

    # Assert all cases captured, and nothing missed.
    # Total: 0+0+2+1+3+2+1+1+3+3+1+2+1+3+1+2+1 = 27
    assert total == sum(map(sum, def_count.values())) == 27
