# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import (
    EnvironmentOperation,
    EnvironmentOperationNotification,
    EnvironmentState,
    OperationRestartRequired,
    OperationRunning,
)


def reduce_environment_state(
    state: EnvironmentState,
    notification: EnvironmentOperationNotification,
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
    notification: EnvironmentOperationNotification,
) -> EnvironmentOperation:
    """Replace package progress and apply changes to named output streams."""
    packages = dict(notification.packages)
    logs = dict(state.logs) if state is not None else {}
    for name, content in notification.logs.items():
        if notification.log_mode == "replace":
            logs[name] = content
        else:
            logs[name] = logs.get(name, "") + content

    return EnvironmentOperation(
        packages=packages,
        logs=logs,
        source=notification.source,
        operation_id=notification.operation_id,
        action=notification.action,
        status=notification.status,
    )
