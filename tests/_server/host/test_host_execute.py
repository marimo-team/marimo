# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from marimo._config.manager import get_default_config_manager
from marimo._host.host import Host
from marimo._host.model import HostState, Running
from marimo._host.transitions import StartRuntime
from marimo._server.host.context import HOST_API_PATH, HostContext
from marimo._server.host.index import WorkspaceIndex
from marimo._server.host.lifespan import OPERATIONS
from marimo._server.host.runtime import SessionManagerRuntime
from marimo._server.lsp import LspServer
from marimo._server.main import create_starlette_app
from marimo._server.session_manager import SessionManager
from marimo._server.workspace import DirectoryWorkspace
from marimo._session.model import SessionMode
from marimo._types.ids import NotebookId, RuntimeId
from tests._server.host.drive import (
    AUTHORITY,
    PORT,
    Response,
    finished,
    notebook_id,
    request,
    wait_for,
)
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

TOKEN = "record-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
RUNTIME = RuntimeId("rt-1")

NOTEBOOK_SOURCE = """import marimo

app = marimo.App()


@app.cell
def _():
    base = 40
    return (base,)


if __name__ == "__main__":
    app.run()
"""


@pytest.fixture
async def served(
    tmp_path: Path,
) -> AsyncIterator[tuple[Starlette, Host, NotebookId]]:
    """A real host over a real kernel, with one notebook's runtime running."""
    (tmp_path / "forecasts.py").write_text(NOTEBOOK_SOURCE)
    manager = SessionManager(
        workspace=DirectoryWorkspace(str(tmp_path), include_markdown=False),
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init(session_manager=manager).apply(app.state)
    runtime = SessionManagerRuntime(manager)
    host = Host(HostState(), runtime, operations=OPERATIONS)
    index = WorkspaceIndex(host, manager.workspace)
    index.refresh()
    runtime.bind(host, index=index)
    app.state.host_context = HostContext(
        host=host,
        runtime=runtime,
        index=index,
        token=TOKEN,
        url=f"http://{AUTHORITY}{HOST_API_PATH}",
        port=PORT,
    )
    forecasts = notebook_id(host, Path("forecasts.py"))
    host.command(StartRuntime(forecasts, RUNTIME, NOW, sandbox=False))
    await wait_for(
        lambda: isinstance(
            host.state.notebooks[forecasts].runtime.lifecycle,  # type: ignore[union-attr]
            Running,
        )
    )
    try:
        yield app, host, forecasts
    finally:
        manager.close_all_sessions()


class Stream:
    """A notebook stream, read in the background, for following executions."""

    def __init__(self, app: Starlette, notebook_id: NotebookId) -> None:
        self.response, self.task, self.disconnect = request(
            app, "GET", f"/notebooks/{notebook_id}/events", headers=AUTH
        )

    async def ready(self) -> None:
        await wait_for(
            lambda: any(
                r.get("event") == "ready" for r in self.response.records
            )
        )

    def about(self, key: str) -> list[dict[str, Any]]:
        records = []
        for record in self.response.records:
            data = record.get("data") or {}
            if (
                record.get("event") == "execution"
                and data["execution"]["id"] == key
            ):
                records.append(record)
            if (
                record.get("event") == "console"
                and data["console"]["execution_id"] == key
            ):
                records.append(record)
        return records

    async def final(self, key: str) -> dict[str, Any]:
        def is_final() -> bool:
            return any(
                r["event"] == "execution"
                and r["data"]["execution"]["status"]
                in ("succeeded", "failed", "interrupted")
                for r in self.about(key)
            )

        await wait_for(is_final, timeout=30)
        executions: list[dict[str, Any]] = [
            r["data"]["execution"]
            for r in self.about(key)
            if r["event"] == "execution"
        ]
        return executions[-1]

    def console(self, key: str) -> str:
        return "".join(
            r["data"]["console"]["text"]
            for r in self.about(key)
            if r["event"] == "console"
        )

    async def close(self) -> None:
        self.disconnect()
        await asyncio.gather(self.task, return_exceptions=True)


async def run(
    app: Starlette, notebook_id: NotebookId, code: str, *, key: str
) -> Response:
    return await finished(
        app,
        "POST",
        f"/notebooks/{notebook_id}/executions",
        headers={**AUTH, "Idempotency-Key": key},
        body=json.dumps({"code": code}).encode(),
    )


async def test_a_run_is_accepted_and_followed_on_the_notebook_stream(
    served: tuple[Starlette, Host, NotebookId],
) -> None:
    app, _, notebook_id = served
    stream = Stream(app, notebook_id)
    await stream.ready()
    try:
        accepted = await run(app, notebook_id, "print(1 + 1)\n3 * 3", key="r1")
        assert accepted.status == 202, accepted.body
        assert accepted.json()["status"] in ("queued", "running")
        assert accepted.json()["id"] == "r1"
        assert accepted.json()["code"] == "print(1 + 1)\n3 * 3"

        done = await stream.final("r1")
        assert done["status"] == "succeeded", done
        assert "9" in done["output"]["data"]
        assert done["errors"] == []
        assert done["started_at"]
        assert done["completed_at"]
        assert stream.console("r1") == "2\n"
        # Every message about the run carries the request's key.
        assert all(r["data"]["request_id"] == "r1" for r in stream.about("r1"))
        statuses = [
            r["data"]["execution"]["status"]
            for r in stream.about("r1")
            if r["event"] == "execution"
        ]
        assert statuses[0] == "running" or statuses[0] == "queued"

        # A repeat answers with the execution as it now is.
        again = await run(app, notebook_id, "print(1 + 1)\n3 * 3", key="r1")
        assert again.status == 202
        assert again.json()["status"] == "succeeded"
    finally:
        await stream.close()


async def test_a_run_that_raises_fails_with_the_exception(
    served: tuple[Starlette, Host, NotebookId],
) -> None:
    app, _, notebook_id = served
    stream = Stream(app, notebook_id)
    await stream.ready()
    try:
        await run(app, notebook_id, "1 / 0", key="r2")
        done = await stream.final("r2")
        assert done["status"] == "failed"
        [error] = done["errors"]
        assert error["kind"] == "exception"
        assert error["name"] == "ZeroDivisionError"
        assert "division" in error["message"]
        # The traceback the kernel printed is text, not the browser's HTML.
        printed = stream.console("r2")
        assert "Traceback" in printed
        assert "ZeroDivisionError" in printed
        assert "<span" not in printed
        assert "codehilite" not in printed
    finally:
        await stream.close()


async def test_a_run_can_be_interrupted_and_blocks_others_meanwhile(
    served: tuple[Starlette, Host, NotebookId],
) -> None:
    app, host, notebook_id = served
    stream = Stream(app, notebook_id)
    await stream.ready()
    try:
        await run(app, notebook_id, "import time\ntime.sleep(60)", key="r3")
        await wait_for(
            lambda: any(
                r["event"] == "execution"
                and r["data"]["execution"]["status"] == "running"
                for r in stream.about("r3")
            )
        )

        other = await run(app, notebook_id, "pass", key="r4")
        assert other.status == 409
        assert json.loads(other.body)["type"].endswith("/conflict")

        interrupt = await finished(
            app,
            "DELETE",
            f"/notebooks/{notebook_id}/executions/r3",
            headers={**AUTH, "Idempotency-Key": "i1"},
        )
        assert interrupt.status == 202
        assert interrupt.json()["id"] == "r3"

        done = await stream.final("r3")
        assert done["status"] == "interrupted"

        # Once final, an interrupt is a conflict.
        late = await finished(
            app,
            "DELETE",
            f"/notebooks/{notebook_id}/executions/r3",
            headers={**AUTH, "Idempotency-Key": "i2"},
        )
        assert late.status == 409
        assert host.state.notebooks[notebook_id].executions["r3"].final  # type: ignore[index]
    finally:
        await stream.close()


async def test_a_run_needs_a_runtime(tmp_path: Path) -> None:
    (tmp_path / "quiet.py").write_text(NOTEBOOK_SOURCE)
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    host = Host(HostState(), MagicMock(), operations=OPERATIONS)
    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()
    app.state.host_context = HostContext(
        host=host,
        runtime=MagicMock(),
        index=index,
        token=TOKEN,
        url=f"http://{AUTHORITY}{HOST_API_PATH}",
        port=PORT,
    )
    quiet = notebook_id(host, Path("quiet.py"))

    refused = await run(app, quiet, "1", key="r5")
    assert refused.status == 409
    assert json.loads(refused.body)["type"].endswith("/no-runtime")
