# Copyright 2025 Marimo. All rights reserved.
import os
import subprocess
import sys

from marimo._runtime.capture import capture_stdout

# 4 methods of execution
#  - script
#  - as a module
#  - In test
# In kernel runtime

# In kernel, setup should just act like another cell, so we focus on the
# behavior here that interacts with the notebook as a script.


def test_acts_like_script() -> None:
    p = subprocess.run(
        [
            sys.executable,
            "tests/_runtime/script_data/script_global_setup_difference.py",
        ],
        capture_output=True,
    )
    assert p.returncode == 0
    result = p.stdout.decode()
    assert result.replace("\r", "") == "*\n1\n"


def test_acts_like_module() -> None:
    # Turn off for recursion guard
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ["PYTEST_CURRENT_TEST"] = ""
    del os.environ["PYTEST_CURRENT_TEST"]

    with capture_stdout() as stdout:
        from tests._runtime.script_data.script_global_setup_difference import (
            injected,
            test_single_run,
        )

    # No 1 since doesn't run app.
    assert stdout.getvalue() == "*\n"
    assert injected == 1

    with capture_stdout() as stdout:
        test_single_run()
    # No rerun on call
    assert stdout.getvalue() == "1\n"

    os.environ["PYTEST_CURRENT_TEST"] = previous


def test_acts_as_test() -> None:
    # Turn off for recursion guard
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ["PYTEST_CURRENT_TEST"] = ""
    del os.environ["PYTEST_CURRENT_TEST"]

    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-rP",
            "-qq",
            "--disable-warnings",
            "--",
            "tests/_runtime/script_data/script_global_setup_difference.py",
        ],
        capture_output=True,
    )
    result = p.stdout.decode()
    assert p.returncode == 0, result
    assert "-\n*\n1\n" in result.replace("\r", "")

    os.environ["PYTEST_CURRENT_TEST"] = previous
