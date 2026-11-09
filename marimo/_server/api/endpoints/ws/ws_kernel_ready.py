# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import (
    ConsumerCapabilities,
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._plugins.core.web_component import JSONType

if TYPE_CHECKING:
    from marimo._session import Session


def build_kernel_ready(
    session: Session,
    resumed: bool,
    ui_values: dict[str, JSONType],
    kiosk: bool,
    auto_instantiated: bool = False,
) -> KernelReadyNotification:
    """Build a KernelReady message.

    Args:
        session: Current session
        resumed: Whether this is a resumed session
        ui_values: UI element values
        kiosk: Whether this is kiosk mode
        auto_instantiated: Whether the kernel has already been instantiated
            server-side (run mode). If True, the frontend does not need
            to instantiate the app.

    Returns:
        KernelReady message operation.
    """
    return KernelReadyNotification(
        layout=session.app_file_manager.read_layout_config(),
        resumed=resumed,
        ui_values=ui_values,
        app_config=session.app_file_manager.app.config,
        kiosk=kiosk,
        consumer_capabilities=(
            ConsumerCapabilities.INTERACTOR
            if kiosk
            else ConsumerCapabilities.EDITOR
        ),
        capabilities=KernelCapabilitiesNotification(),
        auto_instantiated=auto_instantiated,
        stable_session_id=session.stable_id,
    )
