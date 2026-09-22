# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import (
    EnvironmentOperation,
    EnvironmentOperationNotification,
    EnvironmentState,
    OperationRunning,
)
from marimo._session.state.environment import (
    reduce_environment_state,
)


def test_reducer_preserves_previous_state_and_notification() -> None:
    previous = EnvironmentOperation(
        action="install",
        operation_id="install",
        status=OperationRunning(),
        source="kernel",
        packages={"numpy": "running"},
        logs={"numpy": "Installing\n"},
    )
    notification = EnvironmentOperationNotification(
        action="install",
        source="kernel",
        operation_id="install",
        status=OperationRunning(),
        packages={"numpy": "succeeded"},
        logs={"numpy": "Installed\n"},
        log_mode="append",
    )

    environment = EnvironmentState(
        restart_required=False, operations=[previous]
    )
    result = reduce_environment_state(environment, notification)

    assert (environment.operations[0], notification, result.operations[0]) == (
        EnvironmentOperation(
            action="install",
            operation_id="install",
            status=OperationRunning(),
            source="kernel",
            packages={"numpy": "running"},
            logs={"numpy": "Installing\n"},
        ),
        EnvironmentOperationNotification(
            action="install",
            source="kernel",
            operation_id="install",
            status=OperationRunning(),
            packages={"numpy": "succeeded"},
            logs={"numpy": "Installed\n"},
            log_mode="append",
        ),
        EnvironmentOperation(
            action="install",
            operation_id="install",
            status=OperationRunning(),
            source="kernel",
            packages={"numpy": "succeeded"},
            logs={"numpy": "Installing\nInstalled\n"},
        ),
    )
