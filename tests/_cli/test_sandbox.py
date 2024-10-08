from __future__ import annotations

import pytest

from marimo._cli.sandbox import (
    _get_dependencies,
    _pyproject_toml_to_requirements_txt,
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
