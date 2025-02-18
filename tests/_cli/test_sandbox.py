from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from marimo._cli.sandbox import (
    PyProjectReader,
    _is_marimo_dependency,
    _normalize_sandbox_dependencies,
    _pyproject_toml_to_requirements_txt,
    construct_uv_command,
)
from marimo._utils.scripts import read_pyproject_from_script

if TYPE_CHECKING:
    from pathlib import Path


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
    assert PyProjectReader.from_script(SCRIPT).dependencies == [
        "polars",
        "marimo>=0.8.0",
        "quak",
        "vega-datasets",
    ]


def test_get_dependencies_github():
    url = "https://github.com/marimo-team/marimo/blob/a1e1be3190023a86650904249f911b2e6ffb8fac/examples/third_party/leafmap/leafmap_example.py"
    assert PyProjectReader.from_filename(url).dependencies == [
        "leafmap==0.41.0",
        "marimo",
    ]


def test_no_dependencies():
    SCRIPT = """
import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    assert PyProjectReader.from_script(SCRIPT).dependencies == []


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
    assert PyProjectReader(pyproject).python_version == ">=3.11"

    pyproject = {"dependencies": ["polars"]}
    assert PyProjectReader(pyproject).python_version is None

    assert PyProjectReader({}).python_version is None

    pyproject = {"requires-python": {"invalid": "type"}}
    assert PyProjectReader(pyproject).python_version is None


def test_get_dependencies_with_python_version():
    SCRIPT = """
# /// script
# requires-python = ">=3.11"
# dependencies = ["polars"]
# ///

import marimo
"""
    assert PyProjectReader.from_script(SCRIPT).dependencies == ["polars"]

    pyproject = read_pyproject_from_script(SCRIPT)
    assert pyproject is not None
    assert PyProjectReader(pyproject).python_version == ">=3.11"

    SCRIPT_NO_PYTHON = """
# /// script
# dependencies = ["polars"]
# ///

import marimo
"""
    pyproject_no_python = read_pyproject_from_script(SCRIPT_NO_PYTHON)
    assert pyproject_no_python is not None
    assert PyProjectReader(pyproject_no_python).python_version is None
    assert PyProjectReader.from_script(SCRIPT_NO_PYTHON).dependencies == [
        "polars"
    ]


def test_get_dependencies_with_nonexistent_file():
    # Test with a non-existent file
    assert (
        PyProjectReader.from_filename("nonexistent_file.py").dependencies == []
    )

    # Test with empty
    assert PyProjectReader.from_filename("").dependencies == []


@patch("marimo._cli.sandbox.is_editable", return_value=False)
def test_normalize_marimo_dependencies(mock_is_editable: Any):
    # Test adding marimo when not present
    assert _normalize_sandbox_dependencies(["numpy"], "1.0.0") == [
        "numpy",
        "marimo==1.0.0",
    ]
    assert mock_is_editable.call_count == 1

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


def test_normalize_marimo_dependencies_editable():
    deps = _normalize_sandbox_dependencies(["numpy"], "1.0.0")
    assert deps[0] == "numpy"
    assert deps[1].startswith("-e")
    assert "marimo" in deps[1]

    deps = _normalize_sandbox_dependencies(["numpy", "marimo"], "1.0.0")
    assert deps[0] == "numpy"
    assert deps[1].startswith("-e")
    assert "marimo" in deps[1]


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


def test_construct_uv_cmd_with_python_version(tmp_path: Path) -> None:
    # Test Python version requirement is passed through
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
import marimo
    """
    )
    uv_cmd = construct_uv_command(
        ["edit", str(script_path), "--sandbox"], str(script_path)
    )
    assert "--python" in uv_cmd
    assert ">=3.11" in uv_cmd
    assert "--isolated" in uv_cmd
    assert "--no-project" in uv_cmd
    assert "--sandbox" not in uv_cmd


def test_construct_uv_cmd_with_index_urls() -> None:
    pyproject = {
        "tool": {
            "uv": {
                "index-url": "https://custom.pypi.org/simple",
                "extra-index-url": [
                    "https://extra1.pypi.org/simple",
                    "https://extra2.pypi.org/simple",
                ],
            }
        }
    }
    with patch("marimo._cli.sandbox.PyProjectReader.from_filename") as mock:
        mock.return_value = PyProjectReader(pyproject)
        uv_cmd = construct_uv_command(
            ["edit", "test.py", "--sandbox"], "test.py"
        )
        assert "--index-url" in uv_cmd
        assert "https://custom.pypi.org/simple" in uv_cmd
        assert "--extra-index-url" in uv_cmd
        assert "https://extra1.pypi.org/simple" in uv_cmd
        assert "https://extra2.pypi.org/simple" in uv_cmd


def test_construct_uv_cmd_with_index_configs() -> None:
    pyproject = {
        "tool": {
            "uv": {
                "index": [
                    {
                        "name": "torch-gpu",
                        "url": "https://download.pytorch.org/whl/cu124",
                    }
                ]
            }
        }
    }
    with patch("marimo._cli.sandbox.PyProjectReader.from_filename") as mock:
        mock.return_value = PyProjectReader(pyproject)
        uv_cmd = construct_uv_command(
            ["edit", "test.py", "--sandbox"], "test.py"
        )
        assert "--index" in uv_cmd
        assert "https://download.pytorch.org/whl/cu124" in uv_cmd


def test_construct_uv_cmd_with_sandbox_flag() -> None:
    # Test --sandbox flag is removed
    uv_cmd = construct_uv_command(["edit", "test.py", "--sandbox"], "test.py")
    assert "--sandbox" not in uv_cmd


def test_construct_uv_cmd_empty_dependencies() -> None:
    # Test empty dependencies triggers refresh
    with patch("marimo._cli.sandbox.PyProjectReader.from_filename") as mock:
        mock.return_value = PyProjectReader({})
        uv_cmd = construct_uv_command(["edit", "test.py"], "test.py")
        assert "--refresh" in uv_cmd
        assert "--isolated" in uv_cmd
        assert "--no-project" in uv_cmd


def test_construct_uv_cmd_with_complex_args() -> None:
    # Test complex command arguments are preserved
    args = [
        "edit",
        "test.py",
        "--theme",
        "dark",
        "--port",
        "8000",
        "--sandbox",
    ]
    uv_cmd = construct_uv_command(args, "test.py")
    assert "edit" in uv_cmd
    assert "test.py" in uv_cmd
    assert "--theme" in uv_cmd
    assert "dark" in uv_cmd
    assert "--port" in uv_cmd
    assert "8000" in uv_cmd
    assert "--sandbox" not in uv_cmd
