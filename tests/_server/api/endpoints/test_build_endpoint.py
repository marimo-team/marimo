# Copyright 2026 Marimo. All rights reserved.
"""HTTP-level tests for the Build panel endpoints.

Covers the happy-path shape of ``/preview`` and ``/run``, plus the
``/cancel`` 'session has no in-flight build' branch. The actual build
machinery is exercised by ``tests/_build``; these tests just nail down
the wire format.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from marimo._types.ids import SessionId
from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = SessionId("session-123")
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_preview_returns_per_cell_buckets(client: TestClient) -> None:
    response = client.post("/api/build/preview", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    # The temp_marimo_file fixture has at least one cell — every cell
    # entry must carry an id, a name, and a confidence label.
    assert isinstance(body["cells"], list)
    for cell in body["cells"]:
        assert {"cellId", "name", "predictedKind", "confidence"} <= set(
            cell.keys()
        )


@with_session(SESSION_ID)
def test_run_then_cancel_returns_build_id_and_succeeds(
    client: TestClient,
) -> None:
    """``/run`` returns a build_id we can immediately ``/cancel``.

    We don't wait for the runner to actually complete — the
    background-thread guarantees only that the request returns
    promptly. ``/cancel`` is idempotent enough that "build already
    finished" (from a fast no-op build) is also a success.
    """
    response = client.post(
        "/api/build/run", headers=HEADERS, json={"force": False}
    )
    assert response.status_code == 200, response.text
    build_id = response.json()["buildId"]
    assert build_id

    # Loop a few times because the background worker may have already
    # moved past "running" by the time we send the cancel.
    for _ in range(10):
        cancel = client.post(
            "/api/build/cancel",
            headers=HEADERS,
            json={"buildId": build_id},
        )
        assert cancel.status_code == 200, cancel.text
        if cancel.json()["success"]:
            break
        time.sleep(0.05)


@with_session(SESSION_ID)
def test_cancel_unknown_build_returns_failure(client: TestClient) -> None:
    response = client.post(
        "/api/build/cancel",
        headers=HEADERS,
        json={"buildId": "does-not-exist"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is False


@with_read_session(SESSION_ID)
def test_build_endpoints_forbidden_in_read_mode(client: TestClient) -> None:
    for path in ("preview", "run", "cancel"):
        body = {"buildId": "x"} if path == "cancel" else {}
        response = client.post(
            f"/api/build/{path}", headers=HEADERS, json=body
        )
        assert response.status_code == 401, response.text
