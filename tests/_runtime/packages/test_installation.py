# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import pytest

from marimo._environments.errors import SandboxRestartRequired
from marimo._messaging.notification import (
    EnvironmentOperationStatus,
    InstallingPackageAlertNotification,
    OperationCancelled,
    OperationFailed,
    OperationRestartRequired,
    OperationSucceeded,
    PackageStatusType,
)
from marimo._runtime.packages.installation import package_installation


@pytest.mark.parametrize(
    ("packages", "expected"),
    [
        ({"numpy": "installed", "skipped": "queued"}, OperationSucceeded()),
        (
            {"numpy": "failed"},
            OperationFailed(
                error="Failed to install numpy. See installation logs for details."
            ),
        ),
        (
            {"numpy": "failed", "pandas": "restart-required"},
            OperationFailed(
                error="Failed to install numpy. See installation logs for details."
            ),
        ),
        (
            {"numpy": "restart-required"},
            OperationRestartRequired(
                reason="Dependency changes are saved; restart the kernel to apply them."
            ),
        ),
    ],
)
def test_installation_reports_completion_on_scope_exit(
    packages: PackageStatusType, expected: EnvironmentOperationStatus
) -> None:
    notifications: list[InstallingPackageAlertNotification] = []
    with package_installation(
        packages, "server", notifications.append
    ) as operation_id:
        assert notifications == []

    assert notifications == [
        InstallingPackageAlertNotification(
            packages=packages,
            source="server",
            operation_id=operation_id,
            status=expected,
        )
    ]


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (
            RuntimeError("installation failed"),
            OperationFailed(error="installation failed"),
        ),
        (asyncio.CancelledError(), OperationCancelled()),
        (
            SandboxRestartRequired(
                "The manifest requires another Python version"
            ),
            OperationRestartRequired(
                reason="The manifest requires another Python version"
            ),
        ),
    ],
)
def test_installation_reports_errors_and_reraises(
    error: BaseException,
    status: EnvironmentOperationStatus,
) -> None:
    notifications: list[InstallingPackageAlertNotification] = []
    packages: PackageStatusType = {"numpy": "installing"}
    with pytest.raises(type(error), match=str(error) or "^$"):
        with package_installation(
            packages, "kernel", notifications.append
        ) as operation_id:
            raise error

    assert notifications == [
        InstallingPackageAlertNotification(
            packages=packages,
            operation_id=operation_id,
            status=status,
        )
    ]


def test_retries_have_distinct_operation_ids() -> None:
    notifications: list[InstallingPackageAlertNotification] = []
    packages: PackageStatusType = {"numpy": "failed"}
    with package_installation(
        packages, "kernel", notifications.append
    ) as first:
        pass
    with package_installation(
        packages, "kernel", notifications.append
    ) as retry:
        packages["numpy"] = "installed"

    assert first != retry
    assert notifications == [
        InstallingPackageAlertNotification(
            packages={"numpy": "failed"},
            operation_id=first,
            status=OperationFailed(
                error="Failed to install numpy. See installation logs for details."
            ),
        ),
        InstallingPackageAlertNotification(
            packages={"numpy": "installed"},
            operation_id=retry,
            status=OperationSucceeded(),
        ),
    ]
