# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import threading

import pytest

from marimo._environments.errors import SandboxRestartRequired
from marimo._messaging.notification import (
    EnvironmentAction,
    EnvironmentOperationNotification,
    EnvironmentOperationStatus,
    OperationCancelled,
    OperationFailed,
    OperationRestartRequired,
    OperationRunning,
    OperationSucceeded,
    PackageStatusType,
)
from marimo._runtime.packages.operations import (
    EnvironmentOperationReporter,
    environment_operation,
)


@pytest.mark.parametrize(
    ("action", "packages", "expected"),
    [
        ("prepare", {}, OperationSucceeded()),
        ("sync", {}, OperationSucceeded()),
        ("remove", {"numpy": "succeeded"}, OperationSucceeded()),
        (
            "install",
            {"numpy": "succeeded", "skipped": "queued"},
            OperationFailed(
                error="Could not apply changes to skipped. See operation logs for details."
            ),
        ),
        (
            "install",
            {"numpy": "failed", "pandas": "restart-required"},
            OperationFailed(
                error="Could not apply changes to numpy. See operation logs for details."
            ),
        ),
        (
            "install",
            {"numpy": "restart-required"},
            OperationRestartRequired(
                reason="Dependency changes are saved; restart the kernel to apply them."
            ),
        ),
    ],
)
def test_operation_reports_start_and_outcome(
    action: EnvironmentAction,
    packages: PackageStatusType,
    expected: EnvironmentOperationStatus,
) -> None:
    notifications: list[EnvironmentOperationNotification] = []
    with environment_operation(
        action, packages, "server", notifications.append
    ) as operation:
        pass
    assert notifications == [
        EnvironmentOperationNotification(
            action=action,
            source="server",
            packages=packages,
            operation_id=operation.operation_id,
            status=status,
            logs={},
            log_mode="append",
        )
        for status in (OperationRunning(), expected)
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
            SandboxRestartRequired("Python changed"),
            OperationRestartRequired(reason="Python changed"),
        ),
    ],
)
def test_operation_reports_errors_and_reraises(
    error: BaseException,
    status: EnvironmentOperationStatus,
) -> None:
    notifications: list[EnvironmentOperationNotification] = []
    with pytest.raises(type(error), match=str(error) or "^$"):
        with environment_operation(
            "sync", {}, "kernel", notifications.append
        ) as operation:
            raise error
    assert notifications == [
        EnvironmentOperationNotification(
            action="sync",
            source="kernel",
            packages={},
            operation_id=operation.operation_id,
            status=outcome,
            logs={},
            log_mode="append",
        )
        for outcome in (OperationRunning(), status)
    ]


def test_retries_have_distinct_ids_and_do_not_mutate_previous_updates() -> (
    None
):
    notifications: list[EnvironmentOperationNotification] = []
    packages: PackageStatusType = {"numpy": "failed"}
    with environment_operation(
        "install", packages, "kernel", notifications.append
    ) as first:
        pass
    with environment_operation(
        "install", packages, "kernel", notifications.append
    ) as retry:
        packages["numpy"] = "succeeded"
    assert first.operation_id != retry.operation_id
    assert [notification.packages for notification in notifications] == [
        {"numpy": "failed"},
        {"numpy": "failed"},
        {"numpy": "failed"},
        {"numpy": "succeeded"},
    ]


async def test_cancelled_worker_cannot_resume_a_finished_operation() -> None:
    notifications: list[EnvironmentOperationNotification] = []
    entered, release, finished = (threading.Event() for _ in range(3))

    def output(operation: EnvironmentOperationReporter) -> None:
        entered.set()
        try:
            assert release.wait(5)
            operation.update({"numpy": "Late output\n"})
        finally:
            finished.set()

    async def install() -> None:
        with environment_operation(
            "install", {}, "kernel", notifications.append
        ) as operation:
            await asyncio.to_thread(output, operation)

    task = asyncio.create_task(install())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
    assert [notification.status for notification in notifications] == [
        OperationRunning(),
        OperationCancelled(),
    ]
