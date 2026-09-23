# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from marimo._config.config import merge_default_config
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.notification import (
    EnvironmentOperationNotification,
    MissingPackageAlertNotification,
    OperationFailed,
    OperationSucceeded,
)
from marimo._runtime.commands import (
    CommandMessage,
    InstallPackagesCommand,
)
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
)
from marimo._runtime.packages.utils import is_python_isolated
from marimo._runtime.runner import cell_runner
from tests.conftest import MockedKernel, mock_pyodide

if TYPE_CHECKING:
    import pathlib

HAS_UV = DependencyManager.which("uv")


@pytest.mark.skipif(not HAS_UV, reason="uv not installed")
@patch(
    "marimo._runtime.packages.pypi_package_manager.UvPackageManager.is_in_uv_project",
    new=property(lambda _: False),
)
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
@patch(
    "marimo._runtime.packages.pypi_package_manager.UvPackageManager.is_in_uv_project",
    new=property(lambda _: False),
)
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


@mock_pyodide()
async def test_install_missing_packages_micropip(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallPackagesCommand(
                manager="micropip",
                versions={"barbaz": "", "foobar": ""},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["barbaz"]),
            call(["foobar"]),
        ]


@mock_pyodide()
async def test_install_missing_packages_micropip_with_versions(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallPackagesCommand(
                manager="micropip",
                versions={"numpy": "1.22.0", "pandas": "1.5.0"},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["numpy==1.22.0"]),
            call(["pandas==1.5.0"]),
        ]


@mock_pyodide(already_installed=Mock())
async def test_install_missing_packages_micropip_other_modules(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    k.module_registry.modules = lambda: set(
        {"idk", "done", "already_installed"}
    )

    with patch("micropip.install", new_callable=AsyncMock) as mock_install:
        await k.packages_callbacks.install_missing_packages(
            InstallPackagesCommand(
                manager="micropip",
                versions={},
            )
        )
        assert mock_install.call_count == 2
        assert mock_install.call_args_list == [
            call(["done"]),
            call(["idk"]),
        ]


@mock_pyodide()
async def test_missing_packages_hook(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that missing_packages_hook correctly handles missing packages for micropip"""
    k = mocked_kernel.k
    control_requests: list[CommandMessage] = []
    broadcast_messages: list[
        EnvironmentOperationNotification | MissingPackageAlertNotification
    ] = []

    def mock_enqueue(request: CommandMessage) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: EnvironmentOperationNotification
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
                    source="kernel",
                ),
            }

    def reset_package_manager() -> MicropipPackageManager:
        k.packages_callbacks.package_manager = create_package_manager(
            "micropip"
        )
        package_manager = k.packages_callbacks.package_manager
        assert isinstance(package_manager, MicropipPackageManager)
        return package_manager

    with (
        patch(
            "marimo._runtime.callbacks.packages.broadcast_notification",
            mock_broadcast,
        ),
        patch("micropip.install", new_callable=AsyncMock),
    ):
        runner = cast(cell_runner.Runner, MockRunner())

        # Case 1: Auto-install disabled
        package_manager = reset_package_manager()
        control_requests.clear()
        broadcast_messages.clear()
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

        # Case 2: Multiple missing modules
        package_manager = reset_package_manager()
        control_requests.clear()
        broadcast_messages.clear()
        k.module_registry.missing_modules = lambda: {
            "ibis-framework[duckdb]",
            "pandas",
            "scipy",
        }  # type: ignore
        k.packages_callbacks.missing_packages_hook(runner)

        # Should create install request with all missing packages
        assert len(control_requests) == 0
        assert len(broadcast_messages) == 1
        alert = broadcast_messages[0]
        assert isinstance(alert, MissingPackageAlertNotification)
        assert alert.packages == [
            "grouped-one",
            "grouped-two",
            "ibis-framework[duckdb]",
            "numpy",
            "pandas",
            "scipy",
        ]
        assert alert.isolated == is_python_isolated()


def test_missing_packages_hook_pip(
    mocked_kernel: MockedKernel,
) -> None:
    """Test that missing_packages_hook correctly handles missing packages for pip"""
    k = mocked_kernel.k
    control_requests: list[CommandMessage] = []
    broadcast_messages: list[
        EnvironmentOperationNotification | MissingPackageAlertNotification
    ] = []

    def mock_enqueue(request: CommandMessage) -> None:
        control_requests.append(request)

    def mock_broadcast(
        msg: EnvironmentOperationNotification
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
            "marimo._runtime.callbacks.packages.broadcast_notification",
            mock_broadcast,
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
        assert isinstance(request, InstallPackagesCommand)
        assert request.manager == "pip"
        assert request.versions == {
            "ibis-framework[duckdb]": "",
            "numpy": "",
            "pandas": "",
            "scipy": "",
        }

        # Note: The exact sequence might vary, but we should have final success


@pytest.mark.parametrize("succeed", [False, True])
async def test_install_logs_reach_the_stream_from_worker_threads(
    mocked_kernel: MockedKernel,
    succeed: bool,
) -> None:
    """Per-line install logs bind the kernel's stream when the callback
    is created: the callback fires from worker threads, which do not
    carry the kernel's thread-local context, so a bare broadcast there
    is silently dropped."""
    import threading

    k = mocked_kernel.k
    current = k.packages_callbacks.package_manager
    assert current is not None

    fake = Mock(restart_required=False)
    fake.name = current.name
    fake.is_manager_installed.return_value = True
    fake.attempted_to_install.side_effect = lambda package: (
        package == "skipped"
    )
    fake.module_to_package.side_effect = lambda module: module
    fake.package_to_module.side_effect = lambda package: package

    async def install(
        package: str,
        version: str | None = None,
        log_callback: Any = None,
        **kwargs: Any,
    ) -> bool:
        del version, kwargs
        worker = threading.Thread(
            target=log_callback, args=(f"Worker output for {package}\n",)
        )
        worker.start()
        worker.join()
        return succeed or package == "available"

    fake.install = install
    fake.stream_install = partial(PackageManager.stream_install, fake)
    k.packages_callbacks.package_manager = fake

    await k.packages_callbacks.install_missing_packages(
        InstallPackagesCommand(
            manager=fake.name,
            versions={"available": "", "broken": "", "skipped": ""},
            source="server",
        )
    )

    updates = [
        message
        for message in mocked_kernel.stream.operations
        if isinstance(message, EnvironmentOperationNotification)
    ]
    outcome = updates[-1]
    assert isinstance(
        outcome.status, OperationSucceeded if succeed else OperationFailed
    )
    assert outcome.packages == {
        "available": "succeeded",
        "broken": "succeeded" if succeed else "failed",
    }
    assert {
        (update.operation_id, update.action, update.source)
        for update in updates
    } == {(outcome.operation_id, "install", "server")}
    assert all("skipped" not in update.packages for update in updates)
    final_messages = {
        "available": "Successfully installed available\n",
        "broken": (
            "Successfully installed broken\n"
            if succeed
            else "Failed to install broken\n"
        ),
    }
    for package, final_message in final_messages.items():
        logged = [update for update in updates if package in update.logs]
        # Each package starts its own stream, appends worker output, and
        # ends with the outcome line.
        assert (logged[0].logs, logged[0].log_mode) == (
            {package: f"Installing {package}...\n"},
            "replace",
        )
        assert any(
            update.logs.get(package) == f"Worker output for {package}\n"
            for update in logged
        )
        assert (logged[-1].logs, logged[-1].log_mode) == (
            {package: final_message},
            "append",
        )
