# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pathlib
import sys
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from marimo._config.config import merge_default_config
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.notification import (
    InstallingPackageAlertNotification,
    MissingPackageAlertNotification,
)
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
)
from marimo._runtime.packages.utils import is_python_isolated
from marimo._runtime.requests import (
    ControlRequest,
    InstallMissingPackagesRequest,
)
from marimo._runtime.runner import cell_runner
from tests.conftest import MockedKernel

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )
    # Add marimo, skip os
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert "markdown" not in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"os",' not in contents
        assert '"markdown==' in contents

    # Remove marimo, it's still in requirements
    k._maybe_register_cell("0", "import os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_deletion(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add marimo, skip os
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"os",' not in contents

    # Add markdown
    k._maybe_register_cell("1", "import markdown", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"os",' not in contents
        assert '"markdown==' in contents

    # Remove marimo, it's still in requirements
    k._delete_cell("0")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents

    # Remove markdown, still in reqs
    k._delete_cell("1")

    with open(filename) as f:  # noqa: ASYNC230
        contents = f.read()
        assert '"marimo' in contents
        assert '"markdown==' in contents
        assert '"os",' not in contents


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_off(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = False
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
async def test_manage_script_metadata_uv_no_filename(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "uv",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


async def test_manage_script_metadata_pip_noop(
    tmp_path: pathlib.Path, mocked_kernel: MockedKernel
) -> None:
    GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True
    filename = str(tmp_path / "notebook.py")
    # Create empty file
    with open(filename, "w") as f:  # noqa: ASYNC230
        f.write("")

    k = mocked_kernel.k
    await k.rename_file(filename)
    k._update_runtime_from_user_config(
        merge_default_config(
            {
                "package_management": {
                    "manager": "pip",
                }
            },
        )
    )

    # Add
    k._maybe_register_cell("0", "import marimo as mo\nimport os", stale=False)

    with open(filename) as f:  # noqa: ASYNC230
        assert "" == f.read()


@patch.dict(sys.modules, {"pyodide": Mock()})
async def test_install_missing_packages_micropip(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={"barbaz": "", "foobar": ""},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["barbaz"]),
            call(["foobar"]),
        ]


@patch.dict(sys.modules, {"pyodide": Mock()})
async def test_install_missing_packages_micropip_with_versions(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={"numpy": "1.22.0", "pandas": "1.5.0"},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["numpy==1.22.0"]),
            call(["pandas==1.5.0"]),
        ]


@patch.dict(sys.modules, {"pyodide": Mock(), "already_installed": Mock()})
async def test_install_missing_packages_micropip_other_modules(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    k.module_registry.modules = lambda: set(
        {"idk", "done", "already_installed"}
    )

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallMissingPackagesRequest(
                manager="micropip",
                versions={},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["done"]),
            call(["idk"]),
        ]


@patch.dict(sys.modules, {"pyodide": Mock()})
async def test_missing_packages_hook(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that missing_packages_hook correctly handles missing packages for micropip"""
    k = mocked_kernel.k
    control_requests: list[ControlRequest] = []
    broadcast_messages: list[
        InstallingPackageAlertNotification | MissingPackageAlertNotification
    ] = []

    def mock_enqueue(request: ControlRequest) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: InstallingPackageAlertNotification
        | MissingPackageAlertNotification,
        stream: Any = None,
    ) -> None:
        del stream
        broadcast_messages.append(msg)

    k.enqueue_control_request = mock_enqueue

    # Create a mock runner with ModuleNotFoundError
    class MockRunner:
        def __init__(self) -> None:
            self.exceptions = {
                "cell1": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Duplicate
                "cell2": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Has mapping
                "ibis": ModuleNotFoundError(
                    "No module named 'ibis'", name="ibis"
                ),
                "cell3": ManyModulesNotFoundError(
                    package_names=["grouped-one", "grouped-two"],
                    msg="Missing one and two",
                ),
            }

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
        patch("micropip.install", new_callable=AsyncMock),
    ):
        # Case 1: Auto-install enabled
        runner = cast(cell_runner.Runner, MockRunner())
        k.packages_callbacks.package_manager = create_package_manager(
            "micropip"
        )
        package_manager = k.packages_callbacks.package_manager
        assert isinstance(package_manager, MicropipPackageManager)
        k.packages_callbacks.missing_packages_hook(runner)

        # Should create install request
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "numpy": "",
            "ibis-framework[duckdb]": "",
            "grouped-one": "",
            "grouped-two": "",
        }
        assert len(broadcast_messages) == 0

        # Case 2: Auto-install disabled
        control_requests.clear()
        broadcast_messages.clear()
        package_manager.should_auto_install = lambda: False  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should broadcast alert instead of installing
        assert len(control_requests) == 0
        assert len(broadcast_messages) == 1
        alert = broadcast_messages[0]
        assert isinstance(alert, MissingPackageAlertNotification)
        assert alert.packages == [
            "grouped-one",
            "grouped-two",
            "ibis-framework[duckdb]",
            "numpy",
        ]
        assert alert.isolated == is_python_isolated()

        # Case 3: Multiple missing modules
        control_requests.clear()
        broadcast_messages.clear()
        k.module_registry.missing_modules = lambda: {
            "ibis-framework[duckdb]",
            "pandas",
            "scipy",
        }  # type: ignore
        package_manager.should_auto_install = lambda: True  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should create install request with all missing packages
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "grouped-one": "",
            "grouped-two": "",
            "ibis-framework[duckdb]": "",
            "numpy": "",
            "pandas": "",
            "scipy": "",
        }

        # Case 4: Already attempted packages should be filtered
        control_requests.clear()
        broadcast_messages.clear()
        package_manager.attempted_to_install = (
            lambda package: package == "numpy"
        )  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should only include packages not yet attempted
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == package_manager.name
        assert request.versions == {
            "grouped-one": "",
            "grouped-two": "",
            "ibis-framework[duckdb]": "",
            "pandas": "",
            "scipy": "",
        }


def test_missing_packages_hook_pip(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that missing_packages_hook correctly handles missing packages for pip"""
    k = mocked_kernel.k
    control_requests: list[ControlRequest] = []
    broadcast_messages: list[
        InstallingPackageAlertNotification | MissingPackageAlertNotification
    ] = []

    def mock_enqueue(request: ControlRequest) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: InstallingPackageAlertNotification
        | MissingPackageAlertNotification,
        stream: Any = None,
    ) -> None:
        del stream
        broadcast_messages.append(msg)

    k.enqueue_control_request = mock_enqueue

    # Create a mock runner with ModuleNotFoundError
    class MockRunner:
        def __init__(self) -> None:
            self.exceptions = {
                "cell1": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Duplicate
                "cell2": ModuleNotFoundError(
                    "No module named 'numpy'", name="numpy"
                ),
                # Has mapping
                "ibis": ModuleNotFoundError(
                    "No module named 'ibis'", name="ibis"
                ),
            }

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
    ):
        k.packages_callbacks.package_manager = create_package_manager("pip")
        package_manager = k.packages_callbacks.package_manager
        assert isinstance(package_manager, PipPackageManager)
        package_manager.install = AsyncMock()
        runner = cast(cell_runner.Runner, MockRunner())

        # Case 1: Missing modules with auto-install disabled
        k.module_registry.missing_modules = lambda: {"numpy", "pandas"}  # type: ignore
        package_manager.should_auto_install = lambda: False  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should broadcast alert instead of installing
        assert len(control_requests) == 0
        assert len(broadcast_messages) == 1
        alert = broadcast_messages[0]
        assert isinstance(alert, MissingPackageAlertNotification)
        assert alert.packages == ["ibis-framework[duckdb]", "numpy", "pandas"]
        assert alert.isolated == is_python_isolated()

        # Case 2: Multiple missing modules with auto-install enabled
        control_requests.clear()
        broadcast_messages.clear()
        k.module_registry.missing_modules = lambda: {
            "ibis-framework[duckdb]",
            "numpy",
            "pandas",
            "scipy",
        }  # type: ignore
        package_manager.should_auto_install = lambda: True  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should create install request with all missing packages
        assert len(control_requests) == 1
        request = control_requests[0]
        assert isinstance(request, InstallMissingPackagesRequest)
        assert request.manager == "pip"
        assert request.versions == {
            "ibis-framework[duckdb]": "",
            "numpy": "",
            "pandas": "",
            "scipy": "",
        }


async def test_install_missing_packages_with_streaming_logs(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that install_missing_packages uses streaming logs functionality."""
    k = mocked_kernel.k
    broadcast_messages: list[InstallingPackageAlertNotification] = []

    def mock_broadcast(msg, stream=None):
        """Mock the broadcast_notification function to capture alerts"""
        del stream
        if isinstance(msg, InstallingPackageAlertNotification):
            broadcast_messages.append(msg)

    # Mock package manager
    mock_package_manager = Mock(spec=PipPackageManager)
    mock_package_manager.name = "pip"
    mock_package_manager.is_manager_installed.return_value = True
    mock_package_manager.attempted_to_install.return_value = False
    mock_package_manager.package_to_module.return_value = "test_module"

    # Mock successful installation with log callback
    async def mock_install(pkg: str, version=None, log_callback=None):
        del pkg, version
        if log_callback:
            log_callback("Starting installation...\n")
            log_callback("Downloading package...\n")
            log_callback("Installing package...\n")
            log_callback("Installation complete!\n")
        return True

    mock_package_manager.install = AsyncMock(side_effect=mock_install)

    # Set up packages callbacks
    k.packages_callbacks.package_manager = mock_package_manager

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
    ):
        # Create install request
        request = InstallMissingPackagesRequest(
            manager="pip", versions={"numpy": ""}
        )

        await k.packages_callbacks.install_missing_packages(request)

        # Verify broadcast messages
        assert (
            len(broadcast_messages) >= 5
        )  # Initial + start + done + status updates

        # Check that streaming logs were sent
        streaming_alerts = [
            msg for msg in broadcast_messages if msg.logs is not None
        ]
        assert len(streaming_alerts) >= 2  # At least start and done

        # Verify start log
        start_alerts = [
            msg for msg in streaming_alerts if msg.log_status == "start"
        ]
        assert len(start_alerts) == 1
        assert "numpy" in start_alerts[0].logs
        assert "Installing numpy" in start_alerts[0].logs["numpy"]

        # Verify done log
        done_alerts = [
            msg for msg in streaming_alerts if msg.log_status == "done"
        ]
        assert len(done_alerts) == 1
        assert "numpy" in done_alerts[0].logs
        assert "Successfully installed numpy" in done_alerts[0].logs["numpy"]

        # Verify package manager was called with log callback
        mock_package_manager.install.assert_called_once()
        call_args = mock_package_manager.install.call_args
        assert call_args.kwargs.get("log_callback") is not None


async def test_install_missing_packages_streaming_logs_failure(
    mocked_kernel: MockedKernel,
) -> None:
    """Test streaming logs when package installation fails."""
    k = mocked_kernel.k
    broadcast_messages: list[InstallingPackageAlertNotification] = []

    def mock_broadcast(msg, stream=None):
        del stream
        if isinstance(msg, InstallingPackageAlertNotification):
            broadcast_messages.append(msg)

    # Mock package manager
    mock_package_manager = Mock(spec=PipPackageManager)
    mock_package_manager.name = "pip"
    mock_package_manager.is_manager_installed.return_value = True
    mock_package_manager.attempted_to_install.return_value = False
    mock_package_manager.package_to_module.return_value = "test_module"

    # Mock failed installation with log callback
    async def mock_install_fail(pkg: str, version=None, log_callback=None):
        del pkg, version
        if log_callback:
            log_callback("Starting installation...\n")
            log_callback("Error: Package not found\n")
        return False  # Installation failed

    mock_package_manager.install = AsyncMock(side_effect=mock_install_fail)
    k.packages_callbacks.package_manager = mock_package_manager

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
    ):
        request = InstallMissingPackagesRequest(
            manager="pip", versions={"nonexistent-package": ""}
        )

        await k.packages_callbacks.install_missing_packages(request)

        # Verify failure logs were sent
        streaming_alerts = [
            msg for msg in broadcast_messages if msg.logs is not None
        ]
        assert len(streaming_alerts) >= 2

        # Verify done log with failure message
        done_alerts = [
            msg for msg in streaming_alerts if msg.log_status == "done"
        ]
        assert len(done_alerts) == 1
        assert "nonexistent-package" in done_alerts[0].logs
        assert (
            "Failed to install" in done_alerts[0].logs["nonexistent-package"]
        )


async def test_install_missing_packages_streaming_logs_multiple_packages(
    mocked_kernel: MockedKernel,
) -> None:
    """Test streaming logs for multiple packages."""
    k = mocked_kernel.k
    broadcast_messages: list[InstallingPackageAlertNotification] = []

    def mock_broadcast(msg, stream=None):
        del stream
        if isinstance(msg, InstallingPackageAlertNotification):
            broadcast_messages.append(msg)

    # Mock package manager
    mock_package_manager = Mock(spec=PipPackageManager)
    mock_package_manager.name = "pip"
    mock_package_manager.is_manager_installed.return_value = True
    mock_package_manager.attempted_to_install.return_value = False
    mock_package_manager.package_to_module.side_effect = (
        lambda pkg: pkg.replace("-", "_")
    )

    # Track which packages are being installed
    installation_calls = []

    async def mock_install(pkg: str, version=None, log_callback=None):
        del version
        installation_calls.append(pkg)
        if log_callback:
            log_callback(f"Installing {pkg}...\n")
            log_callback(f"Successfully installed {pkg}!\n")
        return True

    mock_package_manager.install = AsyncMock(side_effect=mock_install)
    k.packages_callbacks.package_manager = mock_package_manager

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
    ):
        request = InstallMissingPackagesRequest(
            manager="pip", versions={"numpy": "", "pandas": "", "scipy": ""}
        )

        await k.packages_callbacks.install_missing_packages(request)

        # Verify all packages were processed
        assert len(installation_calls) == 3
        assert set(installation_calls) == {"numpy", "pandas", "scipy"}

        # Verify streaming logs for each package
        streaming_alerts = [
            msg for msg in broadcast_messages if msg.logs is not None
        ]

        # Should have start and done logs for each package
        start_alerts = [
            msg for msg in streaming_alerts if msg.log_status == "start"
        ]
        done_alerts = [
            msg for msg in streaming_alerts if msg.log_status == "done"
        ]

        assert len(start_alerts) == 3
        assert len(done_alerts) == 3

        # Verify each package has its own logs
        packages_in_start_logs = set()
        for alert in start_alerts:
            packages_in_start_logs.update(alert.logs.keys())

        packages_in_done_logs = set()
        for alert in done_alerts:
            packages_in_done_logs.update(alert.logs.keys())

        assert packages_in_start_logs == {"numpy", "pandas", "scipy"}
        assert packages_in_done_logs == {"numpy", "pandas", "scipy"}


async def test_install_missing_packages_no_logs_backward_compatibility(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that package installation still works without streaming logs (backward compatibility)."""
    k = mocked_kernel.k
    broadcast_messages: list[InstallingPackageAlertNotification] = []

    def mock_broadcast(msg, stream=None):
        del stream
        if isinstance(msg, InstallingPackageAlertNotification):
            broadcast_messages.append(msg)

    # Mock package manager that doesn't use log callbacks
    mock_package_manager = Mock(spec=PipPackageManager)
    mock_package_manager.name = "pip"
    mock_package_manager.is_manager_installed.return_value = True
    mock_package_manager.attempted_to_install.return_value = False
    mock_package_manager.package_to_module.return_value = "test_module"

    # Mock installation without using log callback parameter
    async def mock_install_old_style(pkg: str, version=None, **kwargs: Any):
        del version, kwargs, pkg
        # Ignore log_callback if provided (simulating old package managers)
        return True

    mock_package_manager.install = AsyncMock(
        side_effect=mock_install_old_style
    )
    k.packages_callbacks.package_manager = mock_package_manager

    with (
        patch(
            "marimo._runtime.runtime.broadcast_notification", mock_broadcast
        ),
    ):
        request = InstallMissingPackagesRequest(
            manager="pip", versions={"requests": ""}
        )

        await k.packages_callbacks.install_missing_packages(request)

        # Should still work and send basic status updates
        status_alerts = [msg for msg in broadcast_messages if msg.logs is None]
        assert len(status_alerts) >= 2  # At least installing and installed

        # Verify normal package status progression
        package_statuses = []
        for alert in status_alerts:
            if "requests" in alert.packages:
                package_statuses.append(alert.packages["requests"])

        # Should have at least installing and installed statuses
        assert "installed" in package_statuses
        # Note: The exact sequence might vary, but we should have final success
