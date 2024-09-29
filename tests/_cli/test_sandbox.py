from __future__ import annotations

import os

from marimo._cli.sandbox import _get_dependencies


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


def test_get_local_package_dependencies():
    SCRIPT = """
# Copyright 2024 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas @ ~/local/path1",
#     "numpy @ /local/abs/path2",
#     "polars",
#     "-e ~/foo/package1",
#     "--editable ~/bar/package2",
# ]
# ///

import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")
"""
    parsed_deps = _get_dependencies(SCRIPT)
    home_dir = os.path.expanduser("~")
    # test home dirs are expanded
    assert parsed_deps[0].endswith(f"{home_dir}/local/path1")
    # test that abs paths are left alone
    assert parsed_deps[1].endswith("/local/abs/path2")
    # assert that standard pypi package names remain intact
    assert parsed_deps[2] == "polars"
    # check -e and --editable package paths
    assert parsed_deps[3].endswith(f"{home_dir}/foo/package1")
    assert parsed_deps[4].endswith(f"{home_dir}/bar/package2")
