from __future__ import annotations

import sys

import pytest

from marimo._runtime.packages.utils import (
    append_version,
    is_python_isolated,
    split_packages,
)


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


def test_split_packages() -> None:
    assert split_packages("foo") == ["foo"]
    assert split_packages("foo bar") == ["foo", "bar"]
    assert split_packages("foo==1.2.3 bar==4.5.6") == [
        "foo==1.2.3",
        "bar==4.5.6",
    ]
    assert split_packages("foo[extra1,extra2]==1.2.3 bar[extra3]==4.5.6") == [
        "foo[extra1,extra2]==1.2.3",
        "bar[extra3]==4.5.6",
    ]
    assert split_packages("foo -e /path/to/foo") == ["foo -e /path/to/foo"]
    assert split_packages("foo @ /path/to/foo") == ["foo @ /path/to/foo"]
    assert split_packages("foo -e /path/to/foo bar") == [
        "foo -e /path/to/foo",
        "bar",
    ]
    assert split_packages("foo -e /path/to/foo bar -e /path/to/bar") == [
        "foo -e /path/to/foo",
        "bar -e /path/to/bar",
    ]
    assert split_packages("foo @ /path/to/foo bar @ /path/to/bar") == [
        "foo @ /path/to/foo",
        "bar @ /path/to/bar",
    ]
    assert split_packages("foo -e /path/to/foo bar @ /path/to/bar") == [
        "foo -e /path/to/foo",
        "bar @ /path/to/bar",
    ]
    assert split_packages("foo @ /path/to/foo bar -e /path/to/bar") == [
        "foo @ /path/to/foo",
        "bar -e /path/to/bar",
    ]
    assert split_packages("foo[extra1,extra2]==1.2.3") == [
        "foo[extra1,extra2]==1.2.3"
    ]
    assert split_packages("foo[extra1,extra2]==1.2.3 bar[extra3]==4.5.6") == [
        "foo[extra1,extra2]==1.2.3",
        "bar[extra3]==4.5.6",
    ]
    assert split_packages("foo>=1.0,<2.0 bar>3.0") == [
        "foo>=1.0,<2.0",
        "bar>3.0",
    ]
    assert split_packages("foo~=1.0 bar!=2.0") == ["foo~=1.0", "bar!=2.0"]
    assert split_packages("foo==1.0+local.version bar===1.0") == [
        "foo==1.0+local.version",
        "bar===1.0",
    ]
    assert split_packages(
        "foo @ git+https://github.com/user/repo.git@main"
    ) == ["foo @ git+https://github.com/user/repo.git@main"]
    assert split_packages(
        "foo @ git+https://github.com/user/repo.git@main bar==1.0"
    ) == [
        "foo @ git+https://github.com/user/repo.git@main",
        "bar==1.0",
    ]
    assert split_packages(
        "foo[extra1,extra2] @ git+https://github.com/user/repo.git@main"
    ) == ["foo[extra1,extra2] @ git+https://github.com/user/repo.git@main"]
    assert split_packages("foo-bar==1.0 baz_qux==2.0") == [
        "foo-bar==1.0",
        "baz_qux==2.0",
    ]
    assert split_packages("foo.bar==1.0 baz-qux==2.0") == [
        "foo.bar==1.0",
        "baz-qux==2.0",
    ]
    assert split_packages(
        "foo[extra1,extra2] @ file:///path/to/foo bar @ file:///path/to/bar"
    ) == [
        "foo[extra1,extra2] @ file:///path/to/foo",
        "bar @ file:///path/to/bar",
    ]
    assert split_packages(
        "foo @ https://example.com/foo.tar.gz bar @ https://example.com/bar.whl"
    ) == [
        "foo @ https://example.com/foo.tar.gz",
        "bar @ https://example.com/bar.whl",
    ]
    assert split_packages(
        "foo==1.0; python_version>'3.6' bar==2.0; sys_platform=='win32'"
    ) == [
        "foo==1.0; python_version>'3.6'",
        "bar==2.0; sys_platform=='win32'",
    ]
    assert split_packages(
        "foo==1.0; python_version=='3.7.*' bar==2.0; implementation_name=='cpython'"  # noqa: E501
    ) == [
        "foo==1.0; python_version=='3.7.*'",
        "bar==2.0; implementation_name=='cpython'",
    ]
