# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests._server.api.endpoints.ws_helpers import (
    HEADERS as _HEADERS,
    assert_kernel_ready_response,
    create_response,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession


HEADERS = {
    **_HEADERS,
    "Marimo-Session-Id": "123",
}


async def test_connect_kiosk_with_session(client: TestClient) -> None:
    # Create the first session
    with client.websocket_connect(
        "/ws?session_id=123", headers=_HEADERS
    ) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect in kiosk mode
        with client.websocket_connect(
            "/ws?session_id=456&kiosk=true", headers=_HEADERS
        ) as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(
                data,
                create_response(
                    {
                        "kiosk": True,
                        "resumed": True,
                        "consumer_capabilities": {
                            "edit": False,
                            "interact": False,
                        },
                    }
                ),
            )

            # Send document transaction to reorder cells
            response = client.post(
                "/api/document/transaction",
                headers=HEADERS,
                json={
                    "changes": [
                        {
                            "type": "reorder-cells",
                            "cellIds": ["cell-123"],
                        }
                    ],
                },
            )
            assert response.status_code == 200, response.text

            # Assert kiosk session received the document transaction
            data = other_websocket.receive_json()
            assert data["op"] == "notebook-document-transaction"

            # Send run single cell
            response = client.post(
                "/api/kernel/run",
                headers=HEADERS,
                json={
                    "cellIds": ["cell-3"],
                    "codes": ["print('Hello, cell-3')"],
                },
            )

            # Assert kiosk session received a focused cell notification
            data = _receive_until("focus-cell", other_websocket)
            assert data["op"] == "focus-cell"
            assert data["data"]["cell_id"] == "cell-3"


def test_second_edit_connection_joins_as_viewer(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=ed1", headers=_HEADERS
    ) as editor:
        assert_kernel_ready_response(editor.receive_json())

        with client.websocket_connect(
            "/ws?session_id=vw1", headers=_HEADERS
        ) as viewer:
            data = viewer.receive_json()
            assert_kernel_ready_response(
                data,
                create_response(
                    {
                        "kiosk": True,
                        "resumed": True,
                        "consumer_capabilities": {
                            "edit": False,
                            "interact": False,
                        },
                    }
                ),
            )


def test_takeover_ping_pong_preserves_membership(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        assert_kernel_ready_response(ta.receive_json())
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            _receive_until("kernel-ready", tb)

            # Drain both tabs each round so per-tab queues stay aligned: every
            # takeover enqueues one capabilities-changed per tab.
            rounds = [("b", tb, ta), ("a", ta, tb), ("b", tb, ta)]
            for caller, ws_caller, ws_other in rounds:
                resp = client.post(
                    "/api/kernel/takeover",
                    headers={**HEADERS, "Marimo-Session-Id": caller},
                )
                assert resp.status_code == 200, resp.text
                caller_msg = _receive_until("consumer-capabilities", ws_caller)
                other_msg = _receive_until("consumer-capabilities", ws_other)
                assert (
                    caller_msg["data"]["consumer_capabilities"]["edit"] is True
                )
                assert (
                    other_msg["data"]["consumer_capabilities"]["edit"] is False
                )


def test_third_viewer_survives_takeover(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        assert_kernel_ready_response(ta.receive_json())
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            _receive_until("kernel-ready", tb)
            with client.websocket_connect(
                "/ws?session_id=c", headers=_HEADERS
            ) as tc:
                _receive_until("kernel-ready", tc)

                resp = client.post(
                    "/api/kernel/takeover",
                    headers={**HEADERS, "Marimo-Session-Id": "b"},
                )
                assert resp.status_code == 200, resp.text
                _receive_until("consumer-capabilities", tb)

                # New editor (b) broadcasts; the third viewer (c) still gets it.
                resp = client.post(
                    "/api/document/transaction",
                    headers={**HEADERS, "Marimo-Session-Id": "b"},
                    json={
                        "changes": [
                            {"type": "reorder-cells", "cellIds": ["cell-123"]}
                        ]
                    },
                )
                assert resp.status_code == 200, resp.text
                data = _receive_until("notebook-document-transaction", tc)
                assert data["op"] == "notebook-document-transaction"


def test_capabilities_changed_is_not_recorded(client: TestClient) -> None:
    from marimo._messaging.serde import deserialize_kernel_message

    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        assert_kernel_ready_response(ta.receive_json())
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            _receive_until("kernel-ready", tb)
            client.post(
                "/api/kernel/takeover",
                headers={**HEADERS, "Marimo-Session-Id": "b"},
            )
            _receive_until("consumer-capabilities", tb)

            sm = client.app.state.session_manager
            session = next(iter(sm.sessions.values()))
            recorded = [
                deserialize_kernel_message(n).name
                for n in session.session_view.notifications
            ]
            assert "consumer-capabilities" not in recorded


def test_refresh_resumes_as_editor(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=ed1", headers=_HEADERS
    ) as editor:
        assert_kernel_ready_response(editor.receive_json())
    # editor socket closed on block exit -> session is orphaned

    with client.websocket_connect(
        "/ws?session_id=ed2", headers=_HEADERS
    ) as refreshed:
        assert refreshed.receive_json() == {
            "op": "reconnected",
            "data": {"op": "reconnected"},
        }
        assert_kernel_ready_response(
            _receive_until("kernel-ready", refreshed),
            create_response(
                {
                    "resumed": True,
                    "kiosk": False,
                    "consumer_capabilities": {"edit": True, "interact": True},
                }
            ),
        )


def _receive_until(op: str, websocket: WebSocketTestSession) -> dict[str, Any]:
    while True:
        data = websocket.receive_json()
        if data["op"] == op:
            return data
