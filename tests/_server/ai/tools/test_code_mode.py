# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.requires("pydantic_ai")
def test_build_execute_code_toolset_exposes_single_execute_code_tool() -> None:
    from marimo._server.ai.tools.code_mode import build_execute_code_toolset

    toolset = build_execute_code_toolset(MagicMock(), MagicMock())

    assert list(toolset.tools.keys()) == ["execute_code"]
    tool = toolset.tools["execute_code"]
    # The model is told how to use the tool via its description.
    assert tool.description
    assert "scratchpad" in tool.description


@pytest.mark.requires("pydantic_ai")
async def test_execute_code_tool_routes_to_scratchpad_with_credentials() -> (
    None
):
    from marimo._server.ai.tools.code_mode import build_execute_code_toolset

    session = MagicMock()
    request = MagicMock()
    sentinel_result = MagicMock(name="CodeExecutionResult")

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ) as mock_creds,
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
            return_value=sentinel_result,
        ) as mock_run,
        patch("marimo._server.ai.tools.code_mode.AppState") as mock_app_state,
    ):
        app_state_instance = cast(MagicMock, mock_app_state.return_value)
        toolset = build_execute_code_toolset(session, request)
        execute_code = cast(
            Callable[[str], Awaitable[object]],
            toolset.tools["execute_code"].function,
        )

        result = await execute_code("print('hi')")

    assert result is sentinel_result
    # Credentials are derived from the bound request, not model input.
    mock_creds.assert_called_once_with(app_state_instance, request)
    mock_run.assert_awaited_once_with(
        session,
        request,
        code="print('hi')",
        server_url="http://localhost:2718",
        auth_token="secret-token",
    )


@pytest.mark.requires("pydantic_ai")
def test_references_capability_exposes_deferred_reference_bundles() -> None:
    from marimo._server.ai.skills.utils import load_reference
    from marimo._server.ai.tools.code_mode import references_capability

    capabilities = references_capability()
    by_id = {capability.id: capability for capability in capabilities}

    assert set(by_id) == {
        "gotchas",
        "notebook-improvements",
        "rich-representations",
    }
    for capability in capabilities:
        assert capability.defer_loading is True
        assert capability.get_instructions() == [load_reference(capability.id)]

    assert "Name redefinition" in by_id["gotchas"].description
    assert (
        "Improving, optimizing" in by_id["notebook-improvements"].description
    )
    assert "Custom widgets" in by_id["rich-representations"].description
