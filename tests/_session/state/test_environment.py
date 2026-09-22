# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import (
    InstallingPackageAlertNotification,
    OperationRunning,
)
from marimo._session.state.environment import (
    EnvironmentOperation,
    EnvironmentState,
    reduce_environment_state,
)


def test_reducer_preserves_previous_state_and_notification() -> None:
    previous = EnvironmentOperation(
        operation_id="install",
        status=OperationRunning(),
        source="kernel",
        packages={"numpy": "installing"},
        logs={"numpy": "Installing\n"},
    )
    notification = InstallingPackageAlertNotification(
        operation_id="install",
        status=OperationRunning(),
        packages={"numpy": "installed"},
        logs={"numpy": "Installed\n"},
        log_status="done",
    )

    environment = EnvironmentState(
        restart_required=False, operations=[previous]
    )
    result = reduce_environment_state(environment, notification)

    assert (environment.operations[0], notification, result.operations[0]) == (
        EnvironmentOperation(
            operation_id="install",
            status=OperationRunning(),
            source="kernel",
            packages={"numpy": "installing"},
            logs={"numpy": "Installing\n"},
        ),
        InstallingPackageAlertNotification(
            operation_id="install",
            status=OperationRunning(),
            packages={"numpy": "installed"},
            logs={"numpy": "Installed\n"},
            log_status="done",
        ),
        EnvironmentOperation(
            operation_id="install",
            status=OperationRunning(),
            source="kernel",
            packages={"numpy": "installed"},
            logs={"numpy": "Installing\nInstalled\n"},
        ),
    )
