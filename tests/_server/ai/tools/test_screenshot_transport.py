# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._code_mode.screenshot import (
    _ScreenshotBytes,
    _ScreenshotDataUrl,
    _to_data_url,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._output.formatting import try_format
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.scratchpad import extract_result


@pytest.mark.requires("pydantic_ai")
@pytest.mark.parametrize("as_data_url", [False, True])
async def test_screenshot_reaches_model_as_image(as_data_url: bool) -> None:
    from pydantic_ai import Agent, BinaryContent
    from pydantic_ai.messages import (
        ModelMessage,
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from marimo._server.ai.tools.code_mode import build_execute_code_toolset

    png = b"\x89PNG\r\n\x1a\ntransport-test"
    value = (
        _ScreenshotDataUrl(_to_data_url(png))
        if as_data_url
        else _ScreenshotBytes(png)
    )
    formatted = try_format(value)
    assert formatted.mimetype == "image/png"
    assert formatted.data == _to_data_url(png)
    assert base64.b64decode(formatted.data.split(",", 1)[1]) == png
    session = MagicMock()
    session.session_view.cell_notifications = {
        SCRATCH_CELL_ID: CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype=formatted.mimetype,
                data=formatted.data,
            ),
            console=None,
            status="idle",
        )
    }
    result = extract_result(session)
    calls = 0

    def model(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[ToolCallPart("execute_code", {"code": "capture"})]
            )
        images = []
        for message in messages:
            if not isinstance(message, ModelRequest):
                continue
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(
                    part.content, list
                ):
                    images.extend(
                        item
                        for item in part.content
                        if isinstance(item, BinaryContent)
                    )
                if isinstance(part, ToolReturnPart):
                    assert "data:image" not in part.model_response_str()
        assert images == [BinaryContent(data=png, media_type="image/png")]
        return ModelResponse(parts=[TextPart("Image received")])

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost", None),
        ),
        patch("marimo._server.ai.tools.code_mode.AppState"),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new=AsyncMock(return_value=result),
        ),
    ):
        agent = Agent(
            FunctionModel(model),
            toolsets=[build_execute_code_toolset(session, MagicMock())],
        )
        response = await agent.run("Capture the cell")
    assert response.output == "Image received"
    assert calls == 2
