# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import threading

import pytest

from marimo._messaging.notification import (
    EnvironmentOperationNotification,
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


def test_retries_have_distinct_ids_and_do_not_mutate_previous_updates() -> (
    None
):
    notifications: list[EnvironmentOperationNotification] = []
    packages: PackageStatusType = {"numpy": "failed"}
    with environment_operation(
        "install", packages, "kernel", notifications.append
    ):
        pass
    first = notifications[-1]
    with environment_operation(
        "install", packages, "kernel", notifications.append
    ):
        packages["numpy"] = "succeeded"
    retry = notifications[-1]
    assert first.operation_id != retry.operation_id
    assert (first.packages, retry.packages) == (
        {"numpy": "failed"},
        {"numpy": "succeeded"},
    )


@pytest.mark.parametrize(
    "packages",
    [
        {"numpy": "succeeded", "pandas": "queued"},
        {"numpy": "restart-required", "pandas": "failed"},
    ],
)
def test_incomplete_work_cannot_report_success(
    packages: PackageStatusType,
) -> None:
    notifications: list[EnvironmentOperationNotification] = []
    with environment_operation(
        "install", packages, "kernel", notifications.append
    ):
        pass
    status = notifications[-1].status
    assert isinstance(status, OperationFailed)
    assert "pandas" in status.error


@pytest.mark.parametrize(
    ("packages", "expected"),
    [
        ({}, OperationSucceeded()),
        ({"numpy": "succeeded"}, OperationSucceeded()),
        (
            {"numpy": "restart-required", "pandas": "succeeded"},
            OperationRestartRequired(
                reason="Dependency changes are saved; restart the kernel to apply them."
            ),
        ),
    ],
)
def test_completed_work_reports_its_outcome(
    packages: PackageStatusType,
    expected: OperationSucceeded | OperationRestartRequired,
) -> None:
    notifications: list[EnvironmentOperationNotification] = []
    with environment_operation(
        "sync", packages, "kernel", notifications.append
    ):
        pass
    assert [notification.status for notification in notifications] == [
        OperationRunning(),
        expected,
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
