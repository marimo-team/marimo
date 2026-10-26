# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notification import (
    ConsumerCapabilities,
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._utils.parse_dataclass import parse_raw
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import WebSocketTestSession


def receive_notification(websocket: WebSocketTestSession) -> dict[str, Any]:
    """Read a private session notification from the host event stream."""
    while True:
        event = websocket.receive_json()
        assert "event" in event
        if event["event"] == "marimo":
            notification = event["data"]["marimo"]
            return {"op": notification["op"], "data": notification}


def receive_until(op: str, websocket: WebSocketTestSession) -> dict[str, Any]:
    while True:
        data = receive_notification(websocket)
        if data["op"] == op:
            return data


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

    if "consumer_capabilities" not in partial_response:
        kiosk = response.get("kiosk", False)
        response.update(
            {
                "consumer_capabilities": asdict(
                    ConsumerCapabilities.INTERACTOR
                    if kiosk
                    else ConsumerCapabilities.EDITOR
                )
            }
        )

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
    assert data.consumer_capabilities == expected.consumer_capabilities


def assert_parse_ready_response(raw_data: dict[str, Any]) -> None:
    data = parse_raw(raw_data["data"], KernelReadyNotification)
    assert data is not None


QUERY_PARAMS_CASES = [
    (
        urlencode({"query_params": "foo=1&bar=2&bar=3&baz=4"}),
        {"foo": "1", "bar": ["2", "3"], "baz": "4"},
    ),
    ("query_params=&foo=ignored", {}),
    (
        urlencode(
            {
                "query_params": "types=scatter&cursor=page-2&run_id=experiment"
                "&query_params=nested%3Dvalue%26other%3D1&tag=one&tag=two"
                "&empty=&text=a%2Bb+%26+caf%C3%A9"
                "&access_token=secret&refresh_token=secret&session_id=page-session"
            }
        )
        + "&types=marimo&foo=ignored",
        {
            "types": "scatter",
            "cursor": "page-2",
            "run_id": "experiment",
            "query_params": "nested=value&other=1",
            "tag": ["one", "two"],
            "empty": "",
            "text": "a+b & café",
        },
    ),
    ("types=marimo&cursor=expired&foo=1", {}),
]
