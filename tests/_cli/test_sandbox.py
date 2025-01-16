from __future__ import annotations

import pytest

from marimo._cli.sandbox import (
    _get_dependencies,
    _get_python_version_requirement,
    _is_marimo_dependency,
    _normalize_sandbox_dependencies,
    _pyproject_toml_to_requirements_txt,
    _read_pyproject,
    construct_uv_command,
    get_dependencies_from_filename,
)


def test_get_dependencies():
    SCRIPT = """
# Copyright 2024 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "polars",
#     "marimo>=0.8.0",
#     "quak",
#     "vega-datasets",
# ]
# ///

import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    assert _get_dependencies(SCRIPT) == [
        "polars",
        "marimo>=0.8.0",
        "quak",
        "vega-datasets",
    ]


def test_get_dependencies_github():
    url = "https://github.com/marimo-team/marimo/blob/a1e1be3190023a86650904249f911b2e6ffb8fac/examples/third_party/leafmap/leafmap_example.py"
    assert get_dependencies_from_filename(url) == [
        "leafmap==0.41.0",
        "marimo",
    ]


def test_no_dependencies():
    SCRIPT = """
import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    assert _get_dependencies(SCRIPT) == []


def test_pyproject_toml_to_requirements_txt_git_sources():
    pyproject = {
        "dependencies": [
            "marimo",
            "numpy",
            "polars",
            "altair",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "rev": "main",
                    },
                    "numpy": {
                        "git": "https://github.com/numpy/numpy.git",
                        "branch": "main",
                    },
                    "polars": {
                        "git": "https://github.com/pola/polars.git",
                        "branch": "dev",
                    },
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@main",
        "numpy @ git+https://github.com/numpy/numpy.git@main",
        "polars @ git+https://github.com/pola/polars.git@dev",
        "altair",
    ]


def test_pyproject_toml_to_requirements_txt_with_marker():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "tag": "0.1.0",
                        "marker": "python_version >= '3.12'",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@0.1.0; python_version >= '3.12'",  # noqa: E501
        "polars",
    ]


def test_pyproject_toml_to_requirements_txt_with_url_sources():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "url": "https://github.com/marimo-team/marimo/archive/refs/heads/main.zip",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ https://github.com/marimo-team/marimo/archive/refs/heads/main.zip",  # noqa: E501
        "polars",
    ]


def test_pyproject_toml_to_requirements_txt_with_local_path():
    pyproject = {
        "dependencies": [
            "marimo",
            "polars",
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "path": "/Users/me/work/marimo",
                    }
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ /Users/me/work/marimo",
        "polars",
    ]


@pytest.mark.parametrize(
    "version_spec",
    [
        "marimo>=0.1.0",
        "marimo==0.1.0",
        "marimo<=0.1.0",
        "marimo>0.1.0",
        "marimo<0.1.0",
        "marimo~=0.1.0",
    ],
)
def test_pyproject_toml_to_requirements_txt_with_versioned_dependencies(
    version_spec: str,
):
    pyproject = {
        "dependencies": [
            version_spec,
        ],
        "tool": {
            "uv": {
                "sources": {
                    "marimo": {
                        "git": "https://github.com/marimo-team/marimo.git",
                        "rev": "main",
                    },
                }
            }
        },
    }
    assert _pyproject_toml_to_requirements_txt(pyproject) == [
        "marimo @ git+https://github.com/marimo-team/marimo.git@main",
    ]


def test_get_python_version_requirement():
    pyproject = {"requires-python": ">=3.11"}
    assert _get_python_version_requirement(pyproject) == ">=3.11"

    pyproject = {"dependencies": ["polars"]}
    assert _get_python_version_requirement(pyproject) is None

    assert _get_python_version_requirement(None) is None

    pyproject = {"requires-python": {"invalid": "type"}}
    assert _get_python_version_requirement(pyproject) is None


def test_get_dependencies_with_python_version():
    SCRIPT = """
# /// script
# requires-python = ">=3.11"
# dependencies = ["polars"]
# ///

import marimo
"""
    assert _get_dependencies(SCRIPT) == ["polars"]

    pyproject = _read_pyproject(SCRIPT)
    assert pyproject is not None
    assert _get_python_version_requirement(pyproject) == ">=3.11"

    SCRIPT_NO_PYTHON = """
# /// script
# dependencies = ["polars"]
# ///

import marimo
"""
    pyproject_no_python = _read_pyproject(SCRIPT_NO_PYTHON)
    assert pyproject_no_python is not None
    assert _get_python_version_requirement(pyproject_no_python) is None
    assert _get_dependencies(SCRIPT_NO_PYTHON) == ["polars"]


def test_get_dependencies_with_nonexistent_file():
    # Test with a non-existent file
    assert get_dependencies_from_filename("nonexistent_file.py") == []

    # Test with None
    assert get_dependencies_from_filename(None) == []  # type: ignore


def test_normalize_marimo_dependencies():
    # Test adding marimo when not present
    assert _normalize_sandbox_dependencies(["numpy"], "1.0.0") == [
        "numpy",
        "marimo==1.0.0",
    ]

    # Test preferring bracketed version
    assert _normalize_sandbox_dependencies(
        ["marimo", "marimo[extras]", "numpy"], "1.0.0"
    ) == ["numpy", "marimo[extras]==1.0.0"]

    # Test keeping existing version with brackets
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]>=0.1.0", "numpy"], "1.0.0"
    ) == ["numpy", "marimo[extras]>=0.1.0"]

    # Test adding version when none exists
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]", "numpy"], "1.0.0"
    ) == ["numpy", "marimo[extras]==1.0.0"]

    # Test keeping only one marimo dependency
    assert _normalize_sandbox_dependencies(
        ["marimo>=0.1.0", "marimo[extras]>=0.2.0", "numpy"], "1.0.0"
    ) == ["numpy", "marimo[extras]>=0.2.0"]
    assert _normalize_sandbox_dependencies(
        ["marimo", "marimo[extras]>=0.2.0", "numpy"], "1.0.0"
    ) == ["numpy", "marimo[extras]>=0.2.0"]

    # Test various version specifiers are preserved
    version_specs = [
        "==0.1.0",
        ">=0.1.0",
        "<=0.1.0",
        ">0.1.0",
        "<0.1.0",
        "~=0.1.0",
    ]
    for spec in version_specs:
        assert _normalize_sandbox_dependencies(
            [f"marimo{spec}", "numpy"], "1.0.0"
        ) == ["numpy", f"marimo{spec}"]


def test_is_marimo_dependency():
    assert _is_marimo_dependency("marimo")
    assert _is_marimo_dependency("marimo[extras]")
    assert not _is_marimo_dependency("marimo-extras")
    assert not _is_marimo_dependency("marimo-ai")

    # With version specifiers
    assert _is_marimo_dependency("marimo==0.1.0")
    assert _is_marimo_dependency("marimo[extras]>=0.1.0")
    assert _is_marimo_dependency("marimo[extras]==0.1.0")
    assert _is_marimo_dependency("marimo[extras]~=0.1.0")
    assert _is_marimo_dependency("marimo[extras]<=0.1.0")
    assert _is_marimo_dependency("marimo[extras]>=0.1.0")
    assert _is_marimo_dependency("marimo[extras]<=0.1.0")

    # With other packages
    assert not _is_marimo_dependency("numpy")
    assert not _is_marimo_dependency("pandas")
    assert not _is_marimo_dependency("marimo-ai")
    assert not _is_marimo_dependency("marimo-ai==0.1.0")


def test_construct_uv_cmd_marimo_new() -> None:
    uv_cmd = construct_uv_command(["new"], None)
    assert "--refresh" in uv_cmd


def test_construct_uv_cmd_marimo_edit_empty_file() -> None:
    # a file that doesn't yet exist
    uv_cmd = construct_uv_command(["edit", "foo_123.py"], "foo_123.py")
    assert "--refresh" in uv_cmd
    assert uv_cmd[0] == "uv"
    assert uv_cmd[1] == "run"


def test_construct_uv_cmd_marimo_edit_file_no_sandbox(
    temp_marimo_file: str,
) -> None:
    # a file that has no inline metadata yet
    uv_cmd = construct_uv_command(["edit", temp_marimo_file], temp_marimo_file)
    assert "--refresh" in uv_cmd
    assert uv_cmd[0] == "uv"
    assert uv_cmd[1] == "run"


def test_construct_uv_cmd_marimo_edit_sandboxed_file(
    temp_sandboxed_marimo_file: str,
) -> None:
    # a file that has inline metadata; shouldn't refresh the cache, uv
    # --isolated will do the right thing.
    uv_cmd = construct_uv_command(
        ["edit", temp_sandboxed_marimo_file], temp_sandboxed_marimo_file
    )
    assert "--refresh" not in uv_cmd
    assert uv_cmd[0] == "uv"
    assert uv_cmd[1] == "run"
