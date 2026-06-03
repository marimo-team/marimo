# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._messaging.notification import ConsumerCapabilities
from marimo._session.consumer_policy import (
    TakeoverDecision,
    can_take_over_editing,
    initial_capabilities,
)
from marimo._session.model import ConnectionState
from marimo._types.ids import ConsumerId


def _params(*, kiosk: bool) -> MagicMock:
    params = MagicMock()
    params.kiosk = kiosk
    return params


def test_initial_capabilities_editor_when_no_live_editor() -> None:
    session = MagicMock()
    session.connection_state.return_value = ConnectionState.ORPHANED
    caps = initial_capabilities(session, _params(kiosk=False))
    assert caps == ConsumerCapabilities(edit=True, interact=True)


def test_initial_capabilities_viewer_when_live_editor() -> None:
    session = MagicMock()
    session.connection_state.return_value = ConnectionState.OPEN
    caps = initial_capabilities(session, _params(kiosk=False))
    assert caps == ConsumerCapabilities(edit=False, interact=False)


def test_initial_capabilities_viewer_when_kiosk_requested() -> None:
    session = MagicMock()
    session.connection_state.return_value = ConnectionState.ORPHANED
    caps = initial_capabilities(session, _params(kiosk=True))
    assert caps == ConsumerCapabilities(edit=False, interact=False)


def test_can_take_over_editing_allows_locally() -> None:
    assert (
        can_take_over_editing(MagicMock(), ConsumerId("abc"))
        is TakeoverDecision.ALLOW
    )
