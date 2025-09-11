from __future__ import annotations

import sys
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._runtime.packages.package_manager import LogCallback
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    PY_EXE,
    MicropipPackageManager,
    PipPackageManager,
    RyePackageManager,
    UvPackageManager,
)


def test_create_package_managers() -> None:
    assert isinstance(create_package_manager("pip"), PipPackageManager)
    assert isinstance(
        create_package_manager("micropip"), MicropipPackageManager
    )
    assert isinstance(create_package_manager("rye"), RyePackageManager)
    assert isinstance(create_package_manager("uv"), UvPackageManager)

    with pytest.raises(RuntimeError) as e:
        create_package_manager("foobar")
    assert "Unknown package manager" in str(e)


def test_update_script_metadata() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del log_callback
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"foo": "1.0", "bar": "2.0"}

    pm = MockUvPackageManager()
    pm.update_notebook_script_metadata(
        "nb.py",
        packages_to_add=["foo"],
        packages_to_remove=["bar"],
        upgrade=False,
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "foo==1.0"],
        ["uv", "--quiet", "remove", "--script", "nb.py", "bar"],
    ]

    runs_calls.clear()


def test_update_script_metadata_with_version_map() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del log_callback
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"foo": "1.0", "bar": "2.0"}

    pm = MockUvPackageManager()
    # It should ignore when not in the version map
    # as this implies it failed to install
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_add=["baz"], upgrade=False
    )
    assert runs_calls == []

    # It will attempt to uninstall even if not in the version map
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_remove=["baz"], upgrade=False
    )
    assert runs_calls == [
        ["uv", "--quiet", "remove", "--script", "nb.py", "baz"],
    ]


def test_update_script_metadata_with_mapping() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del log_callback
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"ibis": "2.0", "ibis-framework": "2.0", "pyyaml": "1.0"}

    pm = MockUvPackageManager()
    # It should not canonicalize when passed explicitly
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_add=["ibis"], upgrade=False
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "ibis==2.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # case-insensitive
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["yaml"], upgrade=False
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "PyYAML==1.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # and works with brackets
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["ibis"], upgrade=False
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "ibis-framework[duckdb]==2.0",
        ],
    ]


def test_update_script_metadata_marimo_packages() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del log_callback
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {
                "marimo": "0.1.0",
                "marimo-ai": "0.2.0",
                "pandas": "2.0.0",
            }

    pm = MockUvPackageManager()

    # Test 1: Basic package handling
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo-ai",  # Should have version (different package)
            "pandas",  # Should have version
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo-ai==0.2.0",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 2: Marimo package consolidation - should prefer marimo[ai] over marimo
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "marimo[sql]",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "marimo[sql]",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 3: Multiple marimo extras - should use first one
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "marimo[sql]",
            "marimo[recommended]",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "marimo[sql]",
            "marimo[recommended]",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 4: Only plain marimo
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 5: Upgrade
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=["pandas"],
        upgrade=True,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "--upgrade",
            "pandas==2.0.0",
        ],
    ]
    runs_calls.clear()


async def test_uv_pip_install() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del log_callback
            runs_calls.append(command)
            return True

    pm = MockUvPackageManager()
    await pm._install("foo", upgrade=False)
    assert runs_calls == [
        ["uv", "pip", "install", "--compile", "foo", "-p", PY_EXE],
    ]


def test_log_callback_type() -> None:
    """Test that LogCallback type works correctly."""
    captured_logs = []

    def test_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    # Test type annotation works
    callback: LogCallback = test_callback
    callback("test log\n")

    assert len(captured_logs) == 1
    assert captured_logs[0] == "test log\n"


def test_package_manager_run_without_callback() -> None:
    """Test PackageManager.run without log callback (backward compatibility)."""
    pm = PipPackageManager()

    with (
        patch("subprocess.run") as mock_run,
        patch.object(pm, "is_manager_installed", return_value=True),
    ):
        mock_run.return_value.returncode = 0
        result = pm.run(["echo", "test"], log_callback=None)

        assert result is True
        mock_run.assert_called_once_with(["echo", "test"])


def test_package_manager_run_with_callback() -> None:
    """Test PackageManager.run with log callback streams output."""
    pm = PipPackageManager()
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    mock_stdout_lines = [
        b"Installing package...\n",
        b"Successfully installed!\n",
    ]

    with (
        patch("subprocess.Popen") as mock_popen,
        patch("sys.stdout.buffer.write") as mock_buffer_write,
        patch.object(pm, "is_manager_installed", return_value=True),
    ):
        # Mock the subprocess.Popen to return our test output
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = mock_stdout_lines + [
            b""
        ]  # End with empty bytes
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        result = pm.run(["echo", "test"], log_callback=log_callback)

        assert result is True
        assert captured_logs == [
            "Installing package...\n",
            "Successfully installed!\n",
        ]

        # Verify buffer write was called for terminal output
        assert mock_buffer_write.call_count == len(mock_stdout_lines)
        mock_buffer_write.assert_any_call(b"Installing package...\n")
        mock_buffer_write.assert_any_call(b"Successfully installed!\n")


def test_package_manager_run_with_callback_failure() -> None:
    """Test PackageManager.run with log callback handles failure."""
    pm = PipPackageManager()
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    with (
        patch("subprocess.Popen") as mock_popen,
        patch.object(pm, "is_manager_installed", return_value=True),
    ):
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = [
            b"Error occurred\n",
            b"",
        ]  # End with empty bytes
        mock_proc.wait.return_value = 1  # Non-zero return code
        mock_popen.return_value = mock_proc

        result = pm.run(["failing_command"], log_callback=log_callback)

        assert result is False
        assert captured_logs == ["Error occurred\n"]


async def test_pip_install_with_log_callback() -> None:
    """Test PipPackageManager._install with log callback."""
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    class MockPipPackageManager(PipPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del command
            if log_callback:
                log_callback("Installing numpy...\n")
                log_callback("Successfully installed numpy\n")
            return True

    pm = MockPipPackageManager()
    result = await pm._install(
        "numpy", upgrade=False, log_callback=log_callback
    )

    assert result is True
    assert captured_logs == [
        "Installing numpy...\n",
        "Successfully installed numpy\n",
    ]


async def test_uv_install_with_log_callback() -> None:
    """Test UvPackageManager._install with log callback."""
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    class MockUvPackageManager(UvPackageManager):
        def run(
            self,
            command: list[str],
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del command
            if log_callback:
                log_callback("Resolving dependencies...\n")
                log_callback("Installing packages...\n")
            return True

    pm = MockUvPackageManager()
    result = await pm._install(
        "pandas", upgrade=False, log_callback=log_callback
    )

    assert result is True
    assert captured_logs == [
        "Resolving dependencies...\n",
        "Installing packages...\n",
    ]


async def test_micropip_install_with_log_callback() -> None:
    """Test MicropipPackageManager._install with log callback."""
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    pm = MicropipPackageManager()

    mock_micropip = MagicMock()
    mock_micropip.install = AsyncMock(return_value=None)

    with (
        patch("marimo._utils.platform.is_pyodide", return_value=True),
        patch(
            "marimo._runtime.packages.pypi_package_manager.is_pyodide",
            return_value=True,
        ),
        patch.dict(sys.modules, {"micropip": mock_micropip}),
    ):
        result = await pm._install(
            "requests", upgrade=False, log_callback=log_callback
        )

        assert result is True
        assert len(captured_logs) == 2
        assert "Installing requests with micropip" in captured_logs[0]
        assert "Successfully installed requests" in captured_logs[1]


async def test_package_manager_install_method_with_callback() -> None:
    """Test PackageManager.install method passes log_callback to _install."""
    captured_logs = []

    def log_callback(log_line: str) -> None:
        captured_logs.append(log_line)

    class MockPackageManager(PipPackageManager):
        async def _install(
            self,
            package: str,
            *,
            upgrade: bool,
            log_callback: Optional[LogCallback] = None,
        ) -> bool:
            del upgrade
            if log_callback:
                log_callback(f"Installing {package}...\n")
            return True

    pm = MockPackageManager()
    result = await pm.install(
        "test-package", version="1.0.0", log_callback=log_callback
    )

    assert result is True
    assert captured_logs == ["Installing test-package==1.0.0...\n"]


def test_package_manager_run_manager_not_installed() -> None:
    """Test PackageManager.run when manager is not installed."""
    pm = PipPackageManager()

    with patch.object(pm, "is_manager_installed", return_value=False):
        result = pm.run(["test", "command"], log_callback=None)
        assert result is False

        # Should also return False with log callback
        result = pm.run(["test", "command"], log_callback=lambda _: None)
        assert result is False
