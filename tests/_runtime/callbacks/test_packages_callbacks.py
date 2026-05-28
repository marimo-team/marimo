# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._messaging.notification import (
    InstallingPackageAlertNotification,
)
from marimo._runtime.commands import InstallPackagesCommand

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


def _mock_package_manager(
    name: str, *, install_result: bool = True
) -> MagicMock:
    mock_pm = MagicMock()
    mock_pm.name = name
    mock_pm.is_manager_installed.return_value = True
    mock_pm.attempted_to_install.return_value = False
    mock_pm.install = AsyncMock(return_value=install_result)
    # Identity mapping is enough for the cell-rerun bookkeeping.
    mock_pm.package_to_module.side_effect = lambda pkg: pkg
    return mock_pm


def _installing_alerts(
    mocked_kernel: MockedKernel,
) -> list[InstallingPackageAlertNotification]:
    return [
        op
        for op in mocked_kernel.stream.operations
        if isinstance(op, InstallingPackageAlertNotification)
    ]


async def test_install_packages_explicit_installs_only_requested(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    callbacks = k.packages_callbacks
    assert callbacks.package_manager is not None
    manager_name = callbacks.package_manager.name

    mock_pm = _mock_package_manager(manager_name)
    callbacks.package_manager = mock_pm

    await callbacks.install_packages(
        InstallPackagesCommand(
            manager=manager_name,
            versions={"httpx": ""},
            explicit=True,
            upgrade=True,
            group="dev",
        )
    )

    # Only the requested package is installed, with upgrade/group forwarded.
    mock_pm.install.assert_called_once()
    args, kwargs = mock_pm.install.call_args
    assert args[0] == "httpx"
    assert kwargs["upgrade"] is True
    assert kwargs["group"] == "dev"
    assert kwargs["log_callback"] is not None

    # Progress streamed to the install overlay.
    alerts = _installing_alerts(mocked_kernel)
    assert alerts, "expected installing-package-alert notifications"
    assert alerts[-1].packages == {"httpx": "installed"}


async def test_install_packages_explicit_failure_does_not_exclude_module(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    callbacks = k.packages_callbacks
    assert callbacks.package_manager is not None
    manager_name = callbacks.package_manager.name

    mock_pm = _mock_package_manager(manager_name, install_result=False)
    callbacks.package_manager = mock_pm

    excluded_before = set(k.module_registry.excluded_modules)
    await callbacks.install_packages(
        InstallPackagesCommand(
            manager=manager_name,
            versions={"httpx": ""},
            explicit=True,
        )
    )

    # Unlike the missing-packages flow, an explicit install does not exclude
    # the module on failure (so the user can retry).
    assert k.module_registry.excluded_modules == excluded_before
    alerts = _installing_alerts(mocked_kernel)
    assert alerts[-1].packages == {"httpx": "failed"}


async def test_install_packages_explicit_retries_attempted(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    callbacks = k.packages_callbacks
    assert callbacks.package_manager is not None
    manager_name = callbacks.package_manager.name

    mock_pm = _mock_package_manager(manager_name)
    # Simulate a previously-attempted (failed) install.
    mock_pm.attempted_to_install.return_value = True
    callbacks.package_manager = mock_pm

    await callbacks.install_packages(
        InstallPackagesCommand(
            manager=manager_name,
            versions={"httpx": ""},
            explicit=True,
        )
    )

    # Explicit installs ignore the attempted-install guard so retries work.
    mock_pm.install.assert_called_once()


async def test_install_packages_streams_logs_from_worker_thread(
    mocked_kernel: MockedKernel,
) -> None:
    """Regression: package managers stream logs from a worker thread (install
    runs via asyncio.to_thread). The runtime context is thread-local, so those
    log lines must still reach the stream via an explicitly-captured stream."""
    import asyncio

    k = mocked_kernel.k
    callbacks = k.packages_callbacks
    assert callbacks.package_manager is not None
    manager_name = callbacks.package_manager.name

    mock_pm = _mock_package_manager(manager_name)

    async def install_with_worker_logs(
        *_args: object, **kwargs: object
    ) -> bool:
        log_callback = kwargs["log_callback"]
        assert callable(log_callback)
        # Emit from a worker thread, where the thread-local runtime context is
        # unset -- mirrors _run_sync running under asyncio.to_thread.
        await asyncio.to_thread(log_callback, "Resolved 394 packages\n")
        return True

    mock_pm.install = AsyncMock(side_effect=install_with_worker_logs)
    callbacks.package_manager = mock_pm

    await callbacks.install_packages(
        InstallPackagesCommand(
            manager=manager_name, versions={"httpx": ""}, explicit=True
        )
    )

    appended = [
        alert.logs["httpx"]
        for alert in _installing_alerts(mocked_kernel)
        if alert.log_status == "append"
        and alert.logs
        and "httpx" in alert.logs
    ]
    assert any("Resolved 394 packages" in log for log in appended), (
        "worker-thread log line did not reach the stream"
    )


async def test_install_handler_routes_explicit(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    callbacks = k.packages_callbacks
    callbacks.install_packages = AsyncMock()  # type: ignore[method-assign]
    callbacks.install_missing_packages = AsyncMock()  # type: ignore[method-assign]

    await callbacks._handle_install(
        InstallPackagesCommand(
            manager="uv", versions={"httpx": ""}, explicit=True
        )
    )
    callbacks.install_packages.assert_awaited_once()
    callbacks.install_missing_packages.assert_not_awaited()

    callbacks.install_packages.reset_mock()
    callbacks.install_missing_packages.reset_mock()

    await callbacks._handle_install(
        InstallPackagesCommand(manager="uv", versions={"httpx": ""})
    )
    callbacks.install_missing_packages.assert_awaited_once()
    callbacks.install_packages.assert_not_awaited()


if __name__ == "__main__":
    pytest.main([__file__])
