from __future__ import annotations

import pytest

from marimo._utils.inline_script_metadata import (
    PyProjectReader,
    _pyproject_toml_to_requirements_txt,
    is_marimo_dependency,
)
from marimo._utils.scripts import read_pyproject_from_script


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


def test_is_marimo_dependency():
    assert is_marimo_dependency("marimo")
    assert is_marimo_dependency("marimo[extras]")
    assert not is_marimo_dependency("marimo-extras")
    assert not is_marimo_dependency("marimo-ai")

    # With version specifiers
    assert is_marimo_dependency("marimo==0.1.0")
    assert is_marimo_dependency("marimo[extras]>=0.1.0")
    assert is_marimo_dependency("marimo[extras]==0.1.0")
    assert is_marimo_dependency("marimo[extras]~=0.1.0")
    assert is_marimo_dependency("marimo[extras]<=0.1.0")
    assert is_marimo_dependency("marimo[extras]>=0.1.0")
    assert is_marimo_dependency("marimo[extras]<=0.1.0")

    # With other packages
    assert not is_marimo_dependency("numpy")
    assert not is_marimo_dependency("pandas")
    assert not is_marimo_dependency("marimo-ai")
    assert not is_marimo_dependency("marimo-ai==0.1.0")
