# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

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

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@contextmanager
def package_installation(
    packages: PackageStatusType,
    source: Literal["kernel", "server"],
    notify: Callable[[InstallingPackageAlertNotification], None],
) -> Iterator[str]:
    """Identify an attempt and report its result when installation exits.

    Callers update `packages` as installation progresses. Exiting this scope
    ends the attempt even if some packages were skipped and remain queued.
    """
    operation_id = uuid4().hex
    status: EnvironmentOperationStatus
    try:
        yield operation_id
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
        if failed := [
            package
            for package, package_status in packages.items()
            if package_status == "failed"
        ]:
            status = OperationFailed(
                error=f"Failed to install {', '.join(failed)}. See installation logs for details."
            )
        elif "restart-required" in packages.values():
            status = OperationRestartRequired(
                reason="Dependency changes are saved; restart the kernel to apply them."
            )
        else:
            status = OperationSucceeded()
    finally:
        if packages:
            notify(
                InstallingPackageAlertNotification(
                    packages=dict(packages),
                    source=source,
                    operation_id=operation_id,
                    status=status,
                )
            )
