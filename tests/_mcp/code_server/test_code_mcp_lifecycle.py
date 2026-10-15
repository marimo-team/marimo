# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict

import pytest

from tests._mcp.code_server.test_code_server import create_test_app


@pytest.mark.parametrize("timed_out", [False, True])
async def test_execute_code_uses_independent_execution_budget(
    monkeypatch: pytest.MonkeyPatch,
    timed_out: bool,
) -> None:
    from mcp import Client

    from marimo._ai._tools.types import CodeExecutionResult
    from marimo._runtime.commands import (
        CancelScratchpadCommand,
        ScheduleScratchpadCommand,
    )
    from marimo._server.scratchpad import ScratchCellListener
    from tests._server.test_mcp_execution_lifecycle import ExecutionSession

    app = create_test_app()
    session = ExecutionSession()
    app.state.session_manager._repository._sessions["s1"] = session
    observed: list[float] = []

    async def wait(listener: ScratchCellListener, timeout: float) -> None:
        observed.append(timeout)
        listener.timed_out = timed_out
        session.complete()

    monkeypatch.setattr(ScratchCellListener, "wait", wait)
    async with Client(app.state.code_mcp) as client:
        result = await client.call_tool(
            "execute_code", {"session_id": "s1", "code": "print(42)"}
        )
    assert observed == [300.0]
    assert result.structured_content is not None
    expected = CodeExecutionResult(
        success=not timed_out,
        errors=["Execution timed out after 300.0s"] if timed_out else [],
    )
    assert result.structured_content == asdict(expected)
    assert isinstance(session.control_requests[0], ScheduleScratchpadCommand)
    assert len(session.control_requests) == (2 if timed_out else 1)
    if timed_out:
        assert isinstance(session.control_requests[1], CancelScratchpadCommand)
