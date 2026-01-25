# Copyright 2026 Marimo. All rights reserved.
"""Packages worker for read-only operations on the package state.

This worker runs in a daemon thread in the kernel process and handles
package listing requests off the main execution thread, in order to
not block the kernel and also to not be blocked by the kernel.

It is important for package listing requests to run in the kernel,
not the server, because the kernel process may have been started
by a different Python interpreter than the server process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.notification import (
    ListPackagesResultNotification,
    PackagesDependencyTreeResultNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    ListPackagesCommand,
    PackagesCommand,
    PackagesDependencyTreeCommand,
)
from marimo._runtime.runtime import PackagesCallbacks

if TYPE_CHECKING:
    from marimo._messaging.types import Stream
    from marimo._runtime.runtime import PackagesCallbacks
    from marimo._session.queue import QueueType

LOGGER = _loggers.marimo_logger()


def _handle_list_packages(
    request: ListPackagesCommand,
    packages_callbacks: PackagesCallbacks,
    stream: Stream,
) -> None:
    """Handle a list packages request."""
    try:
        packages = packages_callbacks.list_packages()
    except Exception as e:
        LOGGER.exception("Error listing packages: %s", e)
        packages = []

    broadcast_notification(
        ListPackagesResultNotification(
            request_id=request.request_id,
            packages=packages,
        ),
        stream,
    )


def _handle_dependency_tree(
    request: PackagesDependencyTreeCommand,
    packages_callbacks: PackagesCallbacks,
    stream: Stream,
) -> None:
    """Handle a dependency tree request."""
    try:
        tree = packages_callbacks.dependency_tree(request.filename)
    except Exception as e:
        LOGGER.exception("Error getting dependency tree: %s", e)
        tree = None

    broadcast_notification(
        PackagesDependencyTreeResultNotification(
            request_id=request.request_id,
            tree=tree,
        ),
        stream,
    )


def packages_worker(
    packages_queue: QueueType[PackagesCommand],
    packages_callbacks: PackagesCallbacks,
    stream: Stream,
) -> None:
    """Packages worker responsible for fetching the state of a virtual environment.

    Blocks on the queue waiting for requests, processes them,
    and sends results via the stream.

    Args:
        packages_queue: Queue from which requests are pulled.
        packages_callbacks: Object containing the packages_callbacks attribute.
        stream: Stream used to communicate results.
    """
    while True:
        try:
            request = packages_queue.get()
            LOGGER.debug("Packages worker received request: %s", request)

            if isinstance(request, ListPackagesCommand):
                _handle_list_packages(request, packages_callbacks, stream)
            elif isinstance(request, PackagesDependencyTreeCommand):
                _handle_dependency_tree(request, packages_callbacks, stream)
            else:
                LOGGER.warning(
                    "Unknown packages request type: %s", type(request)
                )
        except Exception as e:
            LOGGER.exception("Error in packages worker: %s", e)
