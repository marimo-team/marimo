from __future__ import annotations

import sys

import pytest

from marimo._runtime.packages.utils import append_version, is_python_isolated


# TODO(akshayka): virtualenv not activating on windows CI
@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
def test_is_python_isolated() -> None:
    # tests should always be run in an isolated (non-system) environment;
    # we only run them in a virtualenv, venv, or conda env ...
    assert is_python_isolated()


def test_append_version() -> None:
    assert append_version("foo", "1.2.3") == "foo==1.2.3"
    assert append_version("foo", None) == "foo"
    assert append_version("foo", "") == "foo"
    assert append_version("foo", "latest") == "foo"
