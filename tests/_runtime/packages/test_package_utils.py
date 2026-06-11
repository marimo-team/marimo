from __future__ import annotations

import sys

import pytest

from marimo._runtime.packages.utils import (
    append_version,
    filter_requirements_for_emscripten,
    is_python_isolated,
    marker_environment_for_platform,
    requirement_applies,
    split_packages,
    strip_requirement_name,
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
        "foo==1.0; python_version=='3.7.*' bar==2.0; implementation_name=='cpython'"
    ) == [
        "foo==1.0; python_version=='3.7.*'",
        "bar==2.0; implementation_name=='cpython'",
    ]


def test_strip_requirement_name() -> None:
    assert strip_requirement_name("package==1.0.0") == "package"
    assert strip_requirement_name("package[extra]>=1.0") == "package[extra]"
    assert (
        strip_requirement_name("package>=1.0; python_version>='3.8'")
        == "package"
    )
    assert (
        strip_requirement_name("package @ https://github.com/user/repo.git")
        == "package @ https://github.com/user/repo.git"
    )


def test_requirement_applies_emscripten_markers() -> None:
    emscripten_env = marker_environment_for_platform("emscripten")

    assert (
        requirement_applies(
            "torch>=2.0; sys_platform != 'emscripten'",
            marker_environment=emscripten_env,
        )
        is False
    )
    assert (
        requirement_applies(
            "pyodide-http; sys_platform == 'emscripten'",
            marker_environment=emscripten_env,
        )
        is True
    )
    assert (
        requirement_applies(
            "pandas>=2.0; sys_platform == 'linux'",
            marker_environment=emscripten_env,
        )
        is False
    )
    assert requirement_applies("pandas>=2.0") is True


def test_filter_requirements_for_emscripten() -> None:
    deps = [
        "pandas>=2.0",
        "torch>=2.0; sys_platform != 'emscripten'",
        "pyodide-http; sys_platform == 'emscripten'",
        "jax; sys_platform == 'linux'",
    ]
    assert filter_requirements_for_emscripten(deps) == [
        "pandas>=2.0",
        "pyodide-http; sys_platform == 'emscripten'",
    ]


def test_filter_requirements_for_emscripten_combined_markers() -> None:
    """Combined PEP 508 markers (and) are evaluated on Emscripten."""
    deps = [
        "native; sys_platform != 'emscripten' and python_version >= '3.10'",
        "wasm-only; sys_platform == 'emscripten' and python_version >= '3.10'",
    ]
    assert filter_requirements_for_emscripten(deps) == [
        "wasm-only; sys_platform == 'emscripten' and python_version >= '3.10'",
    ]


def test_strip_requirement_name_url_and_vcs() -> None:
    assert (
        strip_requirement_name(
            "pkg @ git+https://github.com/user/repo.git@main"
        )
        == "pkg @ git+https://github.com/user/repo.git@main"
    )
    assert (
        strip_requirement_name("pkg @ file:///path/to/pkg")
        == "pkg @ file:///path/to/pkg"
    )
    assert (
        strip_requirement_name("pkg[extra1,extra2]===1.0.0")
        == "pkg[extra1,extra2]"
    )


def test_marker_environment_for_platform_overrides_sys_platform() -> None:
    env = marker_environment_for_platform("emscripten")
    assert env["sys_platform"] == "emscripten"
