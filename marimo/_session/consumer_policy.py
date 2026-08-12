# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from marimo._messaging.notification import ConsumerCapabilities
from marimo._session.model import ConnectionState

if TYPE_CHECKING:
    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._session.types import Session
    from marimo._types.ids import ConsumerId


class TakeoverDecision(Enum):
    """Outcome of a takeover request

    **ALLOW**: The takeover request is allowed, and the consumer can take over the session.

    **DENY**: The takeover request is denied, and the consumer cannot take over the session.
    """

    ALLOW = "allow"
    DENY = "deny"


def initial_capabilities(
    session: Session, connection_params: ConnectionParams
) -> ConsumerCapabilities:
    """Determine whether to allow takeover based on initial capabilities."""

    has_live_editor = session.connection_state() == ConnectionState.OPEN

    # A secondary connection defaults to an interactor: it can drive UI state
    # but not edit the notebook. Pure read-only (interact=False) is opt-in, set
    # by a deployment's capability provider rather than the local default.
    if connection_params.kiosk or has_live_editor:
        return ConsumerCapabilities.INTERACTOR

    return ConsumerCapabilities.EDITOR


def can_take_over_editing(
    session: Session, consumer_id: ConsumerId
) -> TakeoverDecision:
    """Whether the `consumer` may take over editing. Local policy, always allow."""
    del (
        session,
        consumer_id,
    )  # Not used in this policy, but may be used in other policies
    return TakeoverDecision.ALLOW
