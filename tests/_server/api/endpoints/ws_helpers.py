# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notification import (
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._utils.parse_dataclass import parse_raw
from tests._server.mocks import token_header


def create_response(
    partial_response: dict[str, Any],
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "cell_ids": ["Hbol"],
        "codes": ["import marimo as mo"],
        "names": ["__"],
        "layout": None,
        "resumed": False,
        "ui_values": {},
        "last_executed_code": {},
        "last_execution_time": {},
        "kiosk": False,
        "configs": [{"disabled": False, "hide_code": False}],
        "app_config": {"width": "full"},
        "capabilities": asdict(KernelCapabilitiesNotification()),
    }
    response.update(partial_response)
    return response


HEADERS = {
    **token_header("fake-token"),
}


def headers(session_id: str) -> dict[str, str]:
    return {
        "Marimo-Session-Id": session_id,
        **token_header("fake-token"),
    }


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: dict[str, Any] | None = None
) -> None:
    if response is None:
        response = create_response({})
    data = parse_raw(raw_data["data"], KernelReadyNotification)
    expected = parse_raw(response, KernelReadyNotification)
    assert data.cell_ids == expected.cell_ids
    assert data.codes == expected.codes
    assert data.names == expected.names
    assert data.layout == expected.layout
    assert data.resumed == expected.resumed
    assert data.ui_values == expected.ui_values
    assert data.configs == expected.configs
    assert data.app_config == expected.app_config
    assert data.kiosk == expected.kiosk
    assert data.last_execution_time == expected.last_execution_time
    assert data.capabilities == expected.capabilities


def assert_parse_ready_response(raw_data: dict[str, Any]) -> None:
    data = parse_raw(raw_data["data"], KernelReadyNotification)
    assert data is not None
