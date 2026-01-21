# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from marimo._cli.cli import main
from marimo._utils.platform import (
    check_shared_memory_available,
    is_pyodide,
    is_windows,
)


class TestIsWindows:
    def test_is_windows_on_win32(self) -> None:
        with patch("marimo._utils.platform.sys.platform", "win32"):
            assert is_windows()

    def test_is_windows_on_cygwin(self) -> None:
        with patch("marimo._utils.platform.sys.platform", "cygwin"):
            assert is_windows()

    def test_is_windows_on_linux(self) -> None:
        with patch("marimo._utils.platform.sys.platform", "linux"):
            assert not is_windows()

    def test_is_windows_on_darwin(self) -> None:
        with patch("marimo._utils.platform.sys.platform", "darwin"):
            assert not is_windows()


class TestIsPyodide:
    def test_is_pyodide_when_not_loaded(self) -> None:
        # By default, pyodide should not be in sys.modules
        assert not is_pyodide()

    def test_is_pyodide_when_loaded(self) -> None:
        with patch(
            "marimo._utils.platform.sys.modules", {"pyodide": object()}
        ):
            assert is_pyodide()


class TestCheckSharedMemoryAvailable:
    def test_shared_memory_available(self) -> None:
        # On a normal system, shared memory should be available
        is_available, error = check_shared_memory_available()
        assert is_available
        assert error == ""

    def test_shared_memory_unavailable_on_pyodide(self) -> None:
        with patch("marimo._utils.platform.is_pyodide", return_value=True):
            is_available, error = check_shared_memory_available()
            assert not is_available
            assert "Pyodide" in error

    def test_shared_memory_oserror(self) -> None:
        with patch("marimo._utils.platform.is_pyodide", return_value=False):
            # Mock the SharedMemory class to raise OSError
            mock_shm_class = type(
                "MockSharedMemory",
                (),
                {
                    "__init__": lambda self, **kwargs: (_ for _ in ()).throw(
                        OSError("Cannot allocate memory")
                    )
                },
            )

            with patch(
                "multiprocessing.shared_memory.SharedMemory", mock_shm_class
            ):
                is_available, error = check_shared_memory_available()
                assert not is_available
                assert "Unable to create shared memory" in error
                assert "Cannot allocate memory" in error
                assert (
                    "Docker" in error
                )  # Should mention Docker as a possible cause

    def test_edit_exits_with_error_when_shared_memory_unavailable(
        self,
    ) -> None:
        runner = CliRunner()
        with patch(
            "marimo._utils.platform.check_shared_memory_available",
            return_value=(False, "Test shared memory error"),
        ):
            result = runner.invoke(
                main,
                ["edit", "--headless", "--no-token", "--skip-update-check"],
            )
            # Should exit with error code 1
            assert result.exit_code == 1
