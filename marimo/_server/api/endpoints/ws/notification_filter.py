# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo import _loggers
from marimo._messaging.notification import (
    CompletionResultNotification,
    FocusCellNotification,
)

LOGGER = _loggers.marimo_logger()

# Operations that are only sent in kiosk mode
KIOSK_ONLY_OPERATIONS = {
    FocusCellNotification.name,
}

# Operations that are excluded from kiosk mode
KIOSK_EXCLUDED_OPERATIONS = {
    CompletionResultNotification.name,
}


def should_filter_operation(op: str, *, is_kiosk: bool) -> bool:
    """Determine if operation should be filtered based on kiosk mode.

    Args:
        op: Operation name to check
        is_kiosk: Whether the connection is in kiosk (viewer) mode

    Returns:
        True if the operation should be filtered (not sent), False
        otherwise.
    """
    if op in KIOSK_ONLY_OPERATIONS and not is_kiosk:
        LOGGER.debug(
            "Ignoring operation %s, not in kiosk mode",
            op,
        )
        return True
    if op in KIOSK_EXCLUDED_OPERATIONS and is_kiosk:
        LOGGER.debug(
            "Ignoring operation %s, in kiosk mode",
            op,
        )
        return True
    return False
