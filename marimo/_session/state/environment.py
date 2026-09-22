# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

from marimo._messaging.notification import (
    EnvironmentOperationStatus,
    InstallingPackageAlertNotification,
    OperationRestartRequired,
    OperationRunning,
    PackageStatusType,
)


class EnvironmentOperation(msgspec.Struct, frozen=True):
    """Current progress and logs for one execution of environment work."""

    operation_id: str
    status: EnvironmentOperationStatus
    packages: PackageStatusType
    logs: dict[str, str]
    source: Literal["kernel", "server"]


class EnvironmentState(msgspec.Struct, frozen=True):
    """Active operations, the latest result, and an outstanding restart."""

    restart_required: bool
    operations: list[EnvironmentOperation]


def reduce_environment_state(
    state: EnvironmentState,
    notification: InstallingPackageAlertNotification,
) -> EnvironmentState:
    """Retain active attempts, the latest result, and outstanding restarts."""
    operations = {
        attempt.operation_id: attempt for attempt in state.operations
    }
    previous = operations.get(notification.operation_id)
    if previous is None or not isinstance(
        notification.status, OperationRunning
    ):
        operations = {
            operation_id: attempt
            for operation_id, attempt in operations.items()
            if isinstance(attempt.status, OperationRunning)
        }
    operations[notification.operation_id] = _reduce_operation(
        previous, notification
    )
    return EnvironmentState(
        # A later mutation cannot confirm that a different kernel was launched.
        restart_required=(
            state.restart_required
            or isinstance(notification.status, OperationRestartRequired)
            or "restart-required" in notification.packages.values()
        ),
        operations=list(operations.values()),
    )


def _reduce_operation(
    state: EnvironmentOperation | None,
    notification: InstallingPackageAlertNotification,
) -> EnvironmentOperation:
    """Reduce an installation update without mutating its inputs.

    Package statuses replace the previous map. Log updates apply per package;
    a log's `start` or `done` does not indicate an installation batch boundary.
    """
    packages = dict(notification.packages)
    logs = (
        {
            package: content
            for package, content in state.logs.items()
            if package in packages
        }
        if state is not None
        else {}
    )

    if notification.logs is not None and notification.log_status is not None:
        for package, content in notification.logs.items():
            if package not in packages:
                continue
            if notification.log_status == "start":
                logs[package] = content
            else:
                logs[package] = logs.get(package, "") + content

    return EnvironmentOperation(
        packages=packages,
        logs=logs,
        source=notification.source,
        operation_id=notification.operation_id,
        status=notification.status,
    )
