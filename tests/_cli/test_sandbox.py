from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from marimo._cli.sandbox import (
    SandboxMode,
    _normalize_sandbox_dependencies,
    construct_uv_command,
    resolve_sandbox_mode,
    run_in_sandbox,
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
    assert os.path.basename(uv_cmd[0]).startswith("uv")
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
    assert os.path.basename(uv_cmd[0]).startswith("uv")
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
    assert os.path.basename(uv_cmd[0]).startswith("uv")
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
    with (
        patch(
            "marimo._cli.sandbox.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA",
            False,
        ),
        patch("marimo._cli.sandbox.click.confirm", return_value=True),
        patch("marimo._cli.sandbox.is_uv_available", return_value=True),
        patch("marimo._cli.sandbox.sys.stdin.isatty", return_value=True),
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


def test_resolve_local_path_line() -> None:
    from marimo._cli.sandbox import _resolve_local_path_line

    d = Path("/project/notebooks")
    _r = lambda p: str((d / p).resolve())  # noqa: E731

    # Plain relative
    assert _resolve_local_path_line("../../mylib", d) == _r("../../mylib")
    # Editable
    assert _resolve_local_path_line("-e ../pkg", d) == f"-e {_r('../pkg')}"
    # Env marker
    result = _resolve_local_path_line("../pkg ; py<'3.12'", d)
    assert _r("../pkg") in result
    assert "py<'3.12'" in result
    # Inline comment
    result = _resolve_local_path_line("../pkg # via foo", d)
    assert _r("../pkg") in result
    assert "# via foo" in result
    # Both marker and comment
    result = _resolve_local_path_line("../pkg ; py<'3.12' # via foo", d)
    assert _r("../pkg") in result
    assert "py<'3.12'" in result
    assert "# via foo" in result
    # Spaces in path
    assert _r("../my lib") in _resolve_local_path_line("../my lib", d)
    # Non-relative unchanged
    assert _resolve_local_path_line("numpy==1.26.0", d) == "numpy==1.26.0"
    assert _resolve_local_path_line("/absolute/path", d) == "/absolute/path"
    assert _resolve_local_path_line("", d) == ""


def test_python_version_override_takes_precedence(tmp_path: Path) -> None:
    """Override beats both PEP 723 metadata and the host interpreter."""
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
        ["edit", str(script_path)],
        str(script_path),
        additional_features=[],
        additional_deps=[],
        python_version_override="3.12",
    )
    python_idx = uv_cmd.index("--python")
    assert uv_cmd[python_idx + 1] == "3.12"
    # Original metadata version should not appear.
    assert ">=3.11" not in uv_cmd


def test_python_version_override_without_metadata(tmp_path: Path) -> None:
    """Override applies even when the script has no requires-python."""
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
        python_version_override="3.12",
    )
    python_idx = uv_cmd.index("--python")
    assert uv_cmd[python_idx + 1] == "3.12"


def _supports_sync() -> bool:
    from marimo._environments.environment import ensure_supported_uv
    from marimo._environments.uv import UvError, is_uv_available

    if not is_uv_available():
        return False
    try:
        ensure_supported_uv()
    except UvError:
        return False
    return True


SUPPORTS_SYNC = _supports_sync()


@pytest.fixture
def _restore_signal_handlers():
    """run_in_sandbox installs forwarding handlers; undo them."""
    import signal

    saved = {
        sig: signal.getsignal(sig)
        for name in ("SIGINT", "SIGTERM", "SIGHUP")
        if (sig := getattr(signal, name, None)) is not None
    }
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.mark.network
@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
@pytest.mark.skipif(
    os.name == "nt", reason="signal forwarding differs on Windows"
)
@pytest.mark.usefixtures("_restore_signal_handlers")
def test_run_in_sandbox_from_script_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The provisioned path: a markdown notebook's manifest is
    synchronized and marimo launches from the script environment."""

    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path.parent / "uv-cache"))

    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        """---
pyproject: |
  dependencies = []
---

# Hello
""",
        encoding="utf-8",
    )

    code = run_in_sandbox(["--version"], name=str(notebook))

    assert code == 0
    # The carrier is deleted after synchronization.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["notebook.md"]


@pytest.mark.network
@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
@pytest.mark.skipif(
    os.name == "nt", reason="signal forwarding differs on Windows"
)
@pytest.mark.usefixtures("_restore_signal_handlers")
def test_run_in_sandbox_without_a_manifest() -> None:
    """No target means no manifest: marimo runs ephemerally."""

    code = run_in_sandbox(["--version"], name=None)

    assert code == 0


def test_sandbox_exit_codes_propagate(tmp_path: Path) -> None:
    """Every sandbox entry point exits with the inner process's code."""
    from unittest.mock import patch as mock_patch

    from click.testing import CliRunner

    from marimo._cli.cli import main as cli_main

    notebook = tmp_path / "nb.py"
    notebook.write_text(
        '# /// script\n# dependencies = ["numpy"]\n# ///\n', encoding="utf-8"
    )
    runner = CliRunner()

    for command, target in (
        (
            ["edit", "--sandbox", str(notebook), "--headless", "--no-token"],
            "marimo._cli.sandbox.run_in_sandbox",
        ),
        (
            ["export", "html", str(notebook), "--sandbox"],
            "marimo._cli.export.commands.run_in_sandbox",
        ),
    ):
        with (
            mock_patch(target, return_value=3),
            mock_patch(
                "marimo._cli.sandbox.maybe_prompt_run_in_sandbox",
                return_value=True,
            ),
        ):
            result = runner.invoke(cli_main, command)
        assert result.exit_code == 3, (command, result.output)


def test_strip_sandbox_args() -> None:
    from marimo._cli.sandbox import _strip_sandbox_args

    assert _strip_sandbox_args(
        ["-m", "marimo", "edit", "--sandbox", "nb.py"]
    ) == ["-m", "marimo", "edit", "nb.py"]
    assert _strip_sandbox_args(
        ["-m", "marimo", "edit", "--sandbox=uv", "nb.py"]
    ) == ["-m", "marimo", "edit", "nb.py"]


def test_no_reprompt_inside_a_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server launched inside a sandbox must not offer to re-wrap
    itself in a second one."""
    from marimo._cli.sandbox import maybe_prompt_run_in_sandbox
    from marimo._config.settings import GLOBAL_SETTINGS

    notebook = tmp_path / "nb.py"
    notebook.write_text(
        '# /// script\n# dependencies = ["numpy"]\n# ///\nimport marimo\n'
    )

    monkeypatch.setattr(GLOBAL_SETTINGS, "MANAGE_SCRIPT_METADATA", False)
    monkeypatch.setattr(GLOBAL_SETTINGS, "SANDBOX_MODE", None)
    monkeypatch.setattr(GLOBAL_SETTINGS, "SANDBOX_BACKEND", "uv")
    assert maybe_prompt_run_in_sandbox(str(notebook)) is False
