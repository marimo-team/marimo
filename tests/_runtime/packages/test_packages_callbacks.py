# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import marimo._runtime.callbacks.packages as callbacks_module
from marimo._messaging.notification import MissingPackageAlertNotification
from marimo._runtime.callbacks.packages import PackagesCallbacks
from marimo._runtime.packages.pypi_package_manager import PipPackageManager

if TYPE_CHECKING:
    import pytest


def test_missing_packages_alert_deduplicates_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifications: list[MissingPackageAlertNotification] = []
    monkeypatch.setattr(
        callbacks_module,
        "broadcast_notification",
        notifications.append,
    )

    callbacks = PackagesCallbacks.__new__(PackagesCallbacks)
    callbacks.package_manager = PipPackageManager()

    # Two missing modules that resolve to the same package (a module and
    # its async variant) must produce a single alert entry.
    callbacks.send_missing_packages_alert(
        {"azure.identity", "azure.identity.aio"}
    )
    assert len(notifications) == 1
    assert notifications[0].packages == ["azure-identity"]
