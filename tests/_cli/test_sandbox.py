from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from marimo._cli.sandbox import (
    _normalize_sandbox_dependencies,
    construct_uv_command,
)
from marimo._utils.inline_script_metadata import PyProjectReader

if TYPE_CHECKING:
    from pathlib import Path


@patch("marimo._cli.sandbox.is_editable", return_value=False)
def test_normalize_marimo_dependencies(mock_is_editable: Any):
    # Test adding marimo when not present
    assert _normalize_sandbox_dependencies(
        ["numpy"], "1.0.0", additional_features=[]
    ) == [
        "numpy",
        "marimo==1.0.0",
    ]
    assert mock_is_editable.call_count == 1

    # Test preferring bracketed version
    assert _normalize_sandbox_dependencies(
        ["marimo", "marimo[extras]", "numpy"], "1.0.0", additional_features=[]
    ) == ["numpy", "marimo[extras]==1.0.0"]

    # Test keeping existing version with brackets
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]>=0.1.0", "numpy"], "1.0.0", additional_features=[]
    ) == ["numpy", "marimo[extras]>=0.1.0"]

    # Test adding version when none exists
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]", "numpy"], "1.0.0", additional_features=[]
    ) == ["numpy", "marimo[extras]==1.0.0"]

    # Test keeping only one marimo dependency
    assert _normalize_sandbox_dependencies(
        ["marimo>=0.1.0", "marimo[extras]>=0.2.0", "numpy"],
        "1.0.0",
        additional_features=[],
    ) == ["numpy", "marimo[extras]>=0.2.0"]
    assert _normalize_sandbox_dependencies(
        ["marimo", "marimo[extras]>=0.2.0", "numpy"],
        "1.0.0",
        additional_features=[],
    ) == ["numpy", "marimo[extras]>=0.2.0"]

    # With additional features
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]", "numpy"], "1.0.0", additional_features=["lsp"]
    ) == ["numpy", "marimo[lsp,extras]==1.0.0"]

    # With multiple additional features
    assert _normalize_sandbox_dependencies(
        ["marimo[extras]", "numpy"],
        "1.0.0",
        additional_features=["lsp", "recommended"],
    ) == ["numpy", "marimo[lsp,recommended,extras]==1.0.0"]

    # With additional features when not present
    assert _normalize_sandbox_dependencies(
        ["marimo", "numpy"], "1.0.0", additional_features=["lsp"]
    ) == ["numpy", "marimo[lsp]==1.0.0"]

    # With duplicate additional features
    # This is ok although it's a bit redundant
    assert _normalize_sandbox_dependencies(
        ["marimo[lsp]", "numpy"], "1.0.0", additional_features=["lsp"]
    ) == ["numpy", "marimo[lsp,lsp]==1.0.0"]

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
            [f"marimo{spec}", "numpy"], "1.0.0", additional_features=[]
        ) == ["numpy", f"marimo{spec}"]


def test_normalize_marimo_dependencies_editable():
    deps = _normalize_sandbox_dependencies(
        ["numpy"], "1.0.0", additional_features=[]
    )
    assert deps[0] == "numpy"
    assert deps[1].startswith("-e")
    assert "marimo" in deps[1]

    deps = _normalize_sandbox_dependencies(
        ["numpy", "marimo"], "1.0.0", additional_features=[]
    )
    assert deps[0] == "numpy"
    assert deps[1].startswith("-e")
    assert "marimo" in deps[1]


def test_construct_uv_cmd_marimo_new() -> None:
    uv_cmd = construct_uv_command(
        ["new"], None, additional_features=[], additional_deps=[]
    )
    assert "--refresh" in uv_cmd


def test_construct_uv_cmd_marimo_edit_empty_file() -> None:
    # a file that doesn't yet exist
    uv_cmd = construct_uv_command(
        ["edit", "foo_123.py"],
        "foo_123.py",
        additional_features=[],
        additional_deps=[],
    )
    assert "--refresh" in uv_cmd
    assert uv_cmd[0] == "uv"
    assert uv_cmd[1] == "run"


def test_construct_uv_cmd_marimo_edit_file_no_sandbox(
    temp_marimo_file: str,
) -> None:
    # a file that has no inline metadata yet
    uv_cmd = construct_uv_command(
        ["edit", temp_marimo_file],
        temp_marimo_file,
        additional_features=[],
        additional_deps=[],
    )
    assert "--refresh" in uv_cmd
    assert uv_cmd[0] == "uv"
    assert uv_cmd[1] == "run"


def test_construct_uv_cmd_marimo_edit_sandboxed_file(
    temp_sandboxed_marimo_file: str,
) -> None:
    # a file that has inline metadata; shouldn't refresh the cache, uv
    # --isolated will do the right thing.
    uv_cmd = construct_uv_command(
        ["edit", temp_sandboxed_marimo_file],
        temp_sandboxed_marimo_file,
        additional_features=[],
        additional_deps=[],
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
        ["edit", str(script_path), "--sandbox"],
        str(script_path),
        additional_features=[],
        additional_deps=[],
    )
    assert "--python" in uv_cmd
    assert ">=3.11" in uv_cmd
    assert "--isolated" in uv_cmd
    assert "--no-project" in uv_cmd
    assert "--compile-bytecode" in uv_cmd
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
        mock.return_value = PyProjectReader(pyproject, config_path=None)
        uv_cmd = construct_uv_command(
            ["edit", "test.py", "--sandbox"],
            "test.py",
            additional_features=[],
            additional_deps=[],
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
        mock.return_value = PyProjectReader(pyproject, config_path=None)
        uv_cmd = construct_uv_command(
            ["edit", "test.py", "--sandbox"],
            name="test.py",
            additional_features=[],
            additional_deps=[],
        )
        assert "--index" in uv_cmd
        assert "https://download.pytorch.org/whl/cu124" in uv_cmd


def test_construct_uv_cmd_with_sandbox_flag() -> None:
    # Test --sandbox flag is removed
    uv_cmd = construct_uv_command(
        ["edit", "test.py", "--sandbox"],
        name="test.py",
        additional_features=[],
        additional_deps=[],
    )
    assert "--sandbox" not in uv_cmd


def test_construct_uv_cmd_empty_dependencies() -> None:
    # Test empty dependencies triggers refresh
    with patch("marimo._cli.sandbox.PyProjectReader.from_filename") as mock:
        mock.return_value = PyProjectReader({}, config_path=None)
        uv_cmd = construct_uv_command(
            ["edit", "test.py"],
            name="test.py",
            additional_features=[],
            additional_deps=[],
        )
        assert "--refresh" in uv_cmd
        assert "--isolated" in uv_cmd
        assert "--compile-bytecode" in uv_cmd
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
    uv_cmd = construct_uv_command(
        args, name="test.py", additional_features=[], additional_deps=[]
    )
    assert "edit" in uv_cmd
    assert "test.py" in uv_cmd
    assert "--theme" in uv_cmd
    assert "dark" in uv_cmd
    assert "--port" in uv_cmd
    assert "8000" in uv_cmd
    assert "--sandbox" not in uv_cmd


def test_construct_uv_cmd_with_additional_deps() -> None:
    # Test additional dependencies are added
    additional_deps = ["numpy>=1.20.0", "pandas"]
    uv_cmd = construct_uv_command(
        ["edit", "test.py"],
        "test.py",
        additional_features=[],
        additional_deps=additional_deps,
    )

    # Get the additional (layered) dependencies
    with_dependencies_index = uv_cmd.index("--with") + 1
    with_dependencies = uv_cmd[with_dependencies_index]

    assert "pandas" in with_dependencies
    assert "numpy>=1.20.0" in with_dependencies


def test_markdown_sandbox(tmp_path: Path) -> None:
    # Test Python version requirement is passed through
    script_path = tmp_path / "test.md"
    script_path.write_text(
        """---
title: Test
pyproject: |
    requires-python = ">=3.11"
    dependencies = ["numpy"]
---

Hello world!"""
    )
    uv_cmd = construct_uv_command(
        ["edit", str(script_path), "--sandbox"],
        str(script_path),
        additional_features=[],
        additional_deps=[],
    )
    assert "--python" in uv_cmd
    assert ">=3.11" in uv_cmd
    assert "--isolated" in uv_cmd
    assert "--no-project" in uv_cmd
    assert "--compile-bytecode" in uv_cmd
    assert "--sandbox" not in uv_cmd

    req_file_index = uv_cmd.index("--with-requirements") + 1
    req_file_path = uv_cmd[req_file_index]
    with open(req_file_path) as f:
        requirements = f.read()
        assert "numpy" in requirements


def test_markdown_header(tmp_path: Path) -> None:
    # Test Python version requirement is passed through
    script_path = tmp_path / "test.md"
    script_path.write_text(
        """---
title: Test
pyproject: |
header: |
    #! /usr/bin/env python
    # /// script
    # requires-python = ">=3.11"
    # dependencies = ["numpy"]
    # ///
    "Other metadata"
---
import marimo
    """
    )
    uv_cmd = construct_uv_command(
        ["edit", str(script_path), "--sandbox"],
        str(script_path),
        additional_features=[],
        additional_deps=[],
    )
    assert "--python" in uv_cmd
    assert ">=3.11" in uv_cmd
    assert "--isolated" in uv_cmd
    assert "--no-project" in uv_cmd
    assert "--compile-bytecode" in uv_cmd
    assert "--sandbox" not in uv_cmd

    req_file_index = uv_cmd.index("--with-requirements") + 1
    req_file_path = uv_cmd[req_file_index]
    with open(req_file_path) as f:
        requirements = f.read()
        assert "numpy" in requirements


def test_markdown_sandbox_and_header(tmp_path: Path) -> None:
    # Test Python version requirement is passed through
    script_path = tmp_path / "test.md"
    script_path.write_text(
        """---
title: Test
pyproject: |
    requires-python = ">=3.11"
    dependencies = ["numpy"]
header: |
    #! /usr/bin/env python
---
import marimo
    """
    )
    uv_cmd = construct_uv_command(
        ["edit", str(script_path), "--sandbox"],
        str(script_path),
        additional_features=[],
        additional_deps=[],
    )
    assert "--python" in uv_cmd
    assert ">=3.11" in uv_cmd
    assert "--isolated" in uv_cmd
    assert "--no-project" in uv_cmd
    assert "--compile-bytecode" in uv_cmd
    assert "--sandbox" not in uv_cmd

    req_file_index = uv_cmd.index("--with-requirements") + 1
    req_file_path = uv_cmd[req_file_index]
    with open(req_file_path) as f:
        requirements = f.read()
        assert "numpy" in requirements
