# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests._server.api.endpoints.ws_helpers import (
    HEADERS as _HEADERS,
    assert_kernel_ready_response,
    create_response,
    receive_notification,
    receive_until,
)
from tests._server.host.drive import socket_snapshot

if TYPE_CHECKING:
    from starlette.testclient import TestClient


HEADERS = {
    **_HEADERS,
    "Marimo-Session-Id": "123",
}


def notebook_id_of(snapshot: list[dict[str, Any]]) -> str:
    return next(
        event["data"]["notebook"]["id"]
        for event in snapshot
        if event["event"] == "notebook"
    )


def new_cell(cell_id: str) -> dict[str, Any]:
    """A host edit that adds a cell, which every consumer hears about."""
    return {
        "kind": "put_cell",
        "base_etag": None,
        "cell": {"id": cell_id, "code": f"{cell_id} = 1"},
    }


async def test_connect_kiosk_with_session(client: TestClient) -> None:
    # Create the first session
    with client.websocket_connect(
        "/ws?session_id=123", headers=_HEADERS
    ) as websocket:
        notebook_id = notebook_id_of(socket_snapshot(websocket))
        editor_ready = receive_notification(websocket)
        assert_kernel_ready_response(editor_ready)

        # Connect in kiosk mode
        with client.websocket_connect(
            "/ws?session_id=456&kiosk=true", headers=_HEADERS
        ) as other_websocket:
            data = receive_notification(other_websocket)
            assert_kernel_ready_response(
                data,
                create_response(
                    {
                        "kiosk": True,
                        "resumed": True,
                        "consumer_capabilities": {
                            "edit": False,
                            "interact": True,
                        },
                    }
                ),
            )

            for _ in range(2):
                assert (
                    receive_notification(other_websocket)["op"]
                    == "environment-state"
                )

            # Edit the notebook through the host
            response = client.post(
                f"/api/marimo/v1/notebooks/{notebook_id}/edits",
                headers={**HEADERS, "Idempotency-Key": "edit-1"},
                json={"changes": [new_cell("fresh")]},
            )
            assert response.status_code == 200, response.text

            # Assert kiosk session received the document transaction
            data = receive_notification(other_websocket)
            assert data["op"] == "notebook-document-transaction"

            # A full save replaces the canonical document. Viewers receive
            # the applied diff even when it includes edits that bypassed the
            # incremental document endpoint during recovery.
            filename = client.app.state.session_manager.workspace.get_unique_file_key()
            assert filename
            replacement_code = editor_ready["data"]["codes"][0] + "\n# saved"
            response = client.post(
                "/api/kernel/save",
                headers=HEADERS,
                json={
                    "cellIds": editor_ready["data"]["cell_ids"],
                    "filename": filename,
                    "codes": [
                        replacement_code,
                        *editor_ready["data"]["codes"][1:],
                    ],
                    "names": editor_ready["data"]["names"],
                    "configs": editor_ready["data"]["configs"],
                },
            )
            assert response.status_code == 200, response.text
            data = receive_until(
                "notebook-document-transaction", other_websocket
            )
            assert any(
                change["type"] == "set-code"
                and change["code"] == replacement_code
                for change in data["data"]["transaction"]["changes"]
            )

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
            data = receive_until("focus-cell", other_websocket)
            assert data["op"] == "focus-cell"
            assert data["data"]["cell_id"] == "cell-3"


def test_second_edit_connection_joins_as_viewer(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=ed1", headers=_HEADERS
    ) as editor:
        assert_kernel_ready_response(receive_notification(editor))

        with client.websocket_connect(
            "/ws?session_id=vw1", headers=_HEADERS
        ) as viewer:
            data = receive_notification(viewer)
            assert_kernel_ready_response(
                data,
                create_response(
                    {
                        "kiosk": True,
                        "resumed": True,
                        "consumer_capabilities": {
                            "edit": False,
                            "interact": True,
                        },
                    }
                ),
            )


def test_takeover_ping_pong_preserves_membership(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        assert_kernel_ready_response(receive_notification(ta))
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            receive_until("kernel-ready", tb)

            # Drain both tabs each round so per-tab queues stay aligned: every
            # takeover enqueues one capabilities-changed per tab.
            rounds = [("b", tb, ta), ("a", ta, tb), ("b", tb, ta)]
            for caller, ws_caller, ws_other in rounds:
                resp = client.post(
                    "/api/kernel/takeover",
                    headers={**HEADERS, "Marimo-Session-Id": caller},
                )
                assert resp.status_code == 200, resp.text
                caller_msg = receive_until("consumer-capabilities", ws_caller)
                other_msg = receive_until("consumer-capabilities", ws_other)
                assert (
                    caller_msg["data"]["consumer_capabilities"]["edit"] is True
                )
                assert (
                    other_msg["data"]["consumer_capabilities"]["edit"] is False
                )


def test_third_viewer_survives_takeover(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        notebook_id = notebook_id_of(socket_snapshot(ta))
        assert_kernel_ready_response(receive_notification(ta))
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            receive_until("kernel-ready", tb)
            with client.websocket_connect(
                "/ws?session_id=c", headers=_HEADERS
            ) as tc:
                receive_until("kernel-ready", tc)

                resp = client.post(
                    "/api/kernel/takeover",
                    headers={**HEADERS, "Marimo-Session-Id": "b"},
                )
                assert resp.status_code == 200, resp.text
                receive_until("consumer-capabilities", tb)

                # New editor (b) broadcasts; the third viewer (c) still gets it.
                resp = client.post(
                    f"/api/marimo/v1/notebooks/{notebook_id}/edits",
                    headers={
                        **HEADERS,
                        "Marimo-Session-Id": "b",
                        "Idempotency-Key": "edit-1",
                    },
                    json={"changes": [new_cell("fresh")]},
                )
                assert resp.status_code == 200, resp.text
                data = receive_until("notebook-document-transaction", tc)
                assert data["op"] == "notebook-document-transaction"


def test_capabilities_changed_is_not_recorded(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=a", headers=_HEADERS) as ta:
        assert_kernel_ready_response(receive_notification(ta))
        with client.websocket_connect(
            "/ws?session_id=b", headers=_HEADERS
        ) as tb:
            receive_until("kernel-ready", tb)
            client.post(
                "/api/kernel/takeover",
                headers={**HEADERS, "Marimo-Session-Id": "b"},
            )
            receive_until("consumer-capabilities", tb)

            sm = client.app.state.session_manager
            session = next(iter(sm.sessions.values()))
            recorded = [
                n.name for n in session.session_view.snapshot_notifications()
            ]
            assert "consumer-capabilities" not in recorded


def test_refresh_resumes_as_editor(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=ed1", headers=_HEADERS
    ) as editor:
        assert_kernel_ready_response(receive_notification(editor))
    # editor socket closed on block exit -> session is orphaned

    with client.websocket_connect(
        "/ws?session_id=ed2", headers=_HEADERS
    ) as refreshed:
        assert receive_notification(refreshed) == {
            "op": "reconnected",
            "data": {"op": "reconnected"},
        }
        assert_kernel_ready_response(
            receive_until("kernel-ready", refreshed),
            create_response(
                {
                    "resumed": True,
                    "kiosk": False,
                    "consumer_capabilities": {"edit": True, "interact": True},
                }
            ),
        )
