import os
from pathlib import Path

from marimo._runtime.pytest import run_pytest

pytest_plugins = ["pytester"]


def test_smoke_test():
    from tests._runtime.script_data.contains_tests import app

    _, lcls = app.run()
    lcls = dict(lcls)

    def_count = {
        "test_parameterized": 3,
        "test_parameterized_collected": 2,
        "test_parameterized_collected2": 2,
        "test_normal_regular": 1,
        "TestParent": 2,
        "test_sanity": 1,
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
            assert response.total == sum([def_count[d] for d in cell.defs]), (
                response.output
            )
            total += response.total

    os.environ["PYTEST_CURRENT_TEST"] = previous
    # put it back on

    assert total == sum(def_count.values()) == 11
