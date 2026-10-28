# Copyright 2026 Marimo. All rights reserved.
"""The kernel-ready notification for a worker session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import (
    ConsumerCapabilities,
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)

if TYPE_CHECKING:
    from marimo._session.notebook import AppFileManager
    from marimo._session.state.session_view import SessionView


def kernel_ready(
    app_manager: AppFileManager, view: SessionView | None
) -> KernelReadyNotification:
    """Describe the app's cells, resumed from `view` when the session has run."""
    app = app_manager.app
    return KernelReadyNotification(
        codes=tuple(app.cell_manager.codes()),
        names=tuple(app.cell_manager.names()),
        configs=tuple(app.cell_manager.configs()),
        cell_ids=tuple(app.cell_manager.cell_ids()),
        layout=app_manager.read_layout_config(),
        resumed=view is not None,
        ui_values=dict(view.ui_values) if view else {},
        last_executed_code=dict(view.last_executed_code) if view else {},
        last_execution_time=dict(view.last_execution_time) if view else {},
        app_config=app.config,
        kiosk=False,
        capabilities=KernelCapabilitiesNotification(),
        consumer_capabilities=ConsumerCapabilities.EDITOR,
    )
