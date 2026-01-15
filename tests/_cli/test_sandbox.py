from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from marimo._cli.sandbox import (
    SandboxMode,
    _ensure_marimo_in_script_metadata,
    _normalize_sandbox_dependencies,
    build_sandbox_venv,
    cleanup_sandbox_dir,
    construct_uv_command,
    resolve_sandbox_mode,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.inline_script_metadata import PyProjectReader

HAS_UV = DependencyManager.which("uv")


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
    assert uv_cmd[0].endswith("uv")
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
    assert uv_cmd[0].endswith("uv")
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
    assert uv_cmd[0].endswith("uv")
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


def test_resolve_sandbox_mode_user_confirms(tmp_path: Path) -> None:
    """Test that resolve_sandbox_mode returns SandboxMode.SINGLE when user types 'y'."""
    # Create a file with dependencies
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """
# /// script
# dependencies = ["numpy"]
# ///
import marimo
    """
    )

    # Mock the prompt to return True (simulating user typing 'y')
    with patch("marimo._cli.sandbox.click.confirm", return_value=True):
        with patch(
            "marimo._cli.sandbox.DependencyManager.which",
            return_value="/usr/bin/uv",
        ):
            with patch(
                "marimo._cli.sandbox.sys.stdin.isatty", return_value=True
            ):
                result = resolve_sandbox_mode(
                    sandbox=None,
                    name=str(script_path),
                )
                assert result is SandboxMode.SINGLE


def test_resolve_sandbox_mode_explicit_single() -> None:
    """Test that resolve_sandbox_mode returns SandboxMode.SINGLE for single file with sandbox=True."""
    result = resolve_sandbox_mode(
        sandbox=True,
        name="test.py",
    )
    assert result is SandboxMode.SINGLE


def test_resolve_sandbox_mode_explicit_false() -> None:
    """Test that resolve_sandbox_mode returns None when sandbox=False."""
    result = resolve_sandbox_mode(
        sandbox=False,
        name="test.py",
    )
    assert result is None


def test_resolve_sandbox_mode_directory(tmp_path: Path) -> None:
    """Test that resolve_sandbox_mode returns SandboxMode.MULTI for directories."""
    dir_path = tmp_path / "notebooks"
    dir_path.mkdir()

    # Directory with sandbox=True returns SandboxMode.MULTI
    result = resolve_sandbox_mode(
        sandbox=True,
        name=str(dir_path),
    )
    assert result is SandboxMode.MULTI


def test_resolve_sandbox_mode_all_cases(tmp_path: Path) -> None:
    """Test resolve_sandbox_mode for all cases."""
    dir_path = tmp_path / "notebooks"
    dir_path.mkdir()
    file_path = tmp_path / "notebook.py"
    file_path.write_text("# test")

    # sandbox=False always returns None
    assert resolve_sandbox_mode(sandbox=False, name=None) is None
    assert resolve_sandbox_mode(sandbox=False, name=str(dir_path)) is None
    assert resolve_sandbox_mode(sandbox=False, name=str(file_path)) is None

    # sandbox=True with None (current dir) -> SandboxMode.MULTI
    assert resolve_sandbox_mode(sandbox=True, name=None) is SandboxMode.MULTI

    # sandbox=True with directory -> SandboxMode.MULTI
    assert (
        resolve_sandbox_mode(sandbox=True, name=str(dir_path))
        is SandboxMode.MULTI
    )

    # sandbox=True with file -> SandboxMode.SINGLE
    assert (
        resolve_sandbox_mode(sandbox=True, name=str(file_path))
        is SandboxMode.SINGLE
    )


def test_construct_uv_cmd_without_python_version(tmp_path: Path) -> None:
    """Test that current Python version is used when not specified."""
    import platform

    # Create a script without requires-python
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """
# /// script
# dependencies = ["numpy"]
# ///
import marimo
    """
    )
    uv_cmd = construct_uv_command(
        ["edit", str(script_path)],
        str(script_path),
        additional_features=[],
        additional_deps=[],
    )
    assert "--python" in uv_cmd
    python_idx = uv_cmd.index("--python")
    assert uv_cmd[python_idx + 1] == platform.python_version()


def test_ensure_marimo_in_script_metadata_adds_marimo(tmp_path: Path) -> None:
    """Test that marimo is added to script metadata when missing."""
    script_path = tmp_path / "test.py"
    script_path.write_text(
        """# /// script
# dependencies = ["numpy"]
# ///
import marimo
"""
    )

    _ensure_marimo_in_script_metadata(str(script_path))

    content = script_path.read_text()
    assert "marimo" in content
    assert "numpy" in content


def test_ensure_marimo_in_script_metadata_noop_when_present(
    tmp_path: Path,
) -> None:
    """Test that file is unchanged when marimo already present."""
    original = """# /// script
# dependencies = ["marimo", "numpy"]
# ///
import marimo
"""
    script_path = tmp_path / "test.py"
    script_path.write_text(original)

    _ensure_marimo_in_script_metadata(str(script_path))

    assert script_path.read_text() == original


def test_ensure_marimo_in_script_metadata_noop_no_metadata(
    tmp_path: Path,
) -> None:
    """Test that file is unchanged when no script metadata exists."""
    original = """import marimo
app = marimo.App()
"""
    script_path = tmp_path / "test.py"
    script_path.write_text(original)

    _ensure_marimo_in_script_metadata(str(script_path))

    assert script_path.read_text() == original


def test_get_sandbox_requirements_adds_additional_deps(tmp_path: Path) -> None:
    """Test that additional deps are added when not present."""
    from marimo._cli.sandbox import get_sandbox_requirements

    script_path = tmp_path / "test.py"
    script_path.write_text(
        """# /// script
# dependencies = ["numpy"]
# ///
import marimo
"""
    )

    with patch("marimo._cli.sandbox.is_editable", return_value=False):
        reqs = get_sandbox_requirements(
            str(script_path),
            additional_deps=["pyzmq", "msgspec"],
        )

    assert any("numpy" in r for r in reqs)
    assert "pyzmq" in reqs
    assert "msgspec" in reqs


def test_get_sandbox_requirements_no_duplicate_deps(tmp_path: Path) -> None:
    """Test that additional deps aren't duplicated if already present."""
    from marimo._cli.sandbox import get_sandbox_requirements

    script_path = tmp_path / "test.py"
    script_path.write_text(
        """# /// script
# dependencies = ["numpy", "pyzmq>=25.0"]
# ///
import marimo
"""
    )

    with patch("marimo._cli.sandbox.is_editable", return_value=False):
        reqs = get_sandbox_requirements(
            str(script_path),
            additional_deps=["pyzmq", "msgspec"],
        )

    # Should have only one pyzmq entry (uv resolves versions, so it may be ==X.Y.Z)
    pyzmq_entries = [r for r in reqs if "pyzmq" in r.lower()]
    assert len(pyzmq_entries) == 1
    assert "msgspec" in reqs


def test_get_sandbox_requirements_none_filename() -> None:
    """Test get_sandbox_requirements with None filename."""
    from marimo._cli.sandbox import get_sandbox_requirements

    with patch("marimo._cli.sandbox.is_editable", return_value=False):
        reqs = get_sandbox_requirements(None, additional_deps=["pyzmq"])

    # Should have marimo and additional deps
    assert any("marimo" in r for r in reqs)
    assert "pyzmq" in reqs


def test_cleanup_sandbox_dir_removes_directory(tmp_path: Path) -> None:
    """Test that cleanup_sandbox_dir removes the directory."""
    from marimo._cli.sandbox import cleanup_sandbox_dir

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "file.txt").write_text("test")

    cleanup_sandbox_dir(str(sandbox_dir))

    assert not sandbox_dir.exists()


def test_cleanup_sandbox_dir_handles_none() -> None:
    """Test that cleanup_sandbox_dir handles None gracefully."""
    from marimo._cli.sandbox import cleanup_sandbox_dir

    cleanup_sandbox_dir(None)  # Should not raise


def test_cleanup_sandbox_dir_handles_nonexistent(tmp_path: Path) -> None:
    """Test that cleanup_sandbox_dir handles nonexistent directory."""
    from marimo._cli.sandbox import cleanup_sandbox_dir

    nonexistent = str(tmp_path / "does_not_exist")
    cleanup_sandbox_dir(nonexistent)  # Should not raise


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_build_sandbox_venv_creates_venv(tmp_path: Path) -> None:
    """Test venv is created and returns paths."""
    script = tmp_path / "test.py"
    script.write_text("# /// script\n# dependencies = []\n# ///\n")

    sandbox_dir, venv_python = build_sandbox_venv(str(script))
    try:
        assert os.path.isdir(sandbox_dir)
        assert os.path.exists(venv_python)
        assert "python" in venv_python
    finally:
        cleanup_sandbox_dir(sandbox_dir)


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_build_sandbox_venv_with_additional_deps(tmp_path: Path) -> None:
    """Test additional deps are passed through."""
    from marimo._session._venv import get_ipc_kernel_deps

    script = tmp_path / "test.py"
    script.write_text("# /// script\n# dependencies = []\n# ///\n")

    sandbox_dir, venv_python = build_sandbox_venv(
        str(script), additional_deps=get_ipc_kernel_deps()
    )
    try:
        assert os.path.isdir(sandbox_dir)
        assert os.path.exists(venv_python)
    finally:
        cleanup_sandbox_dir(sandbox_dir)
