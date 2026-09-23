# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

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

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class EnvironmentOperationReporter:
    """Report one operation; callers update the package map as work proceeds."""

    def __init__(
        self,
        action: EnvironmentAction,
        packages: PackageStatusType,
        source: Literal["kernel", "server"],
        notify: Callable[[EnvironmentOperationNotification], None],
    ) -> None:
        self._operation_id = uuid4().hex
        self._action = action
        self.packages = packages
        self._source = source
        self._notify = notify
        self._lock = Lock()
        self._finished = False

    def update(
        self, logs: dict[str, str] | None = None, *, replace: bool = False
    ) -> None:
        self._send(OperationRunning(), logs or {}, replace=replace)

    def _send(
        self,
        status: EnvironmentOperationStatus,
        logs: dict[str, str],
        *,
        replace: bool = False,
    ) -> None:
        with self._lock:
            # A cancelled worker may still deliver output after scope exit.
            if self._finished:
                return
            self._notify(
                EnvironmentOperationNotification(
                    operation_id=self._operation_id,
                    action=self._action,
                    status=status,
                    source=self._source,
                    packages=dict(self.packages),
                    logs=dict(logs),
                    log_mode="replace" if replace else "append",
                )
            )
            # Only a delivered outcome closes the operation.
            self._finished = not isinstance(status, OperationRunning)


@contextmanager
def environment_operation(
    action: EnvironmentAction,
    packages: PackageStatusType,
    source: Literal["kernel", "server"],
    notify: Callable[[EnvironmentOperationNotification], None],
) -> Iterator[EnvironmentOperationReporter]:
    """Publish an operation's start and its outcome, including empty syncs."""
    operation = EnvironmentOperationReporter(action, packages, source, notify)
    operation.update()
    status: EnvironmentOperationStatus
    try:
        yield operation
    except (asyncio.CancelledError, KeyboardInterrupt):
        status = OperationCancelled()
        raise
    except SandboxRestartRequired as exc:
        status = OperationRestartRequired(reason=str(exc))
        raise
    except BaseException as exc:
        status = OperationFailed(error=str(exc) or type(exc).__name__)
        raise
    else:
        if incomplete := [
            package
            for package, package_status in packages.items()
            if package_status in ("queued", "running", "failed")
        ]:
            status = OperationFailed(
                error=f"Could not apply changes to {', '.join(incomplete)}. See operation logs for details."
            )
        elif "restart-required" in packages.values():
            status = OperationRestartRequired(
                reason="Dependency changes are saved; restart the kernel to apply them."
            )
        else:
            status = OperationSucceeded()
    finally:
        operation._send(status, {})
