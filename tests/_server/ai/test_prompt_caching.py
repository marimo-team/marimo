# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._config.types import CopilotMode
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.prompts import get_chat_system_prompt
from marimo._server.ai.providers import AnthropicProvider
from marimo._server.ai.tools.types import ToolDefinition


@pytest.mark.requires("anthropic", "pydantic_ai")
@pytest.mark.parametrize("mode", ["ask", "agent"])
@patch("marimo._server.ai.providers.get_tool_manager", new=MagicMock())
async def test_anthropic_chat_preserves_cached_prefix(
    mode: CopilotMode,
) -> None:
    import httpx2
    from anthropic import AsyncAnthropic
    from pydantic_ai.providers.anthropic import (
        AnthropicProvider as PydanticAnthropic,
    )
    from pydantic_ai.ui.vercel_ai import VercelAIAdapter

    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "Done"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 1,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 20,
                },
            },
        )

    initial = {
        "id": "user-1",
        "role": "user",
        "parts": [
            {
                "type": "data-marimo-notebook",
                "data": {
                    "sessionId": "session-1",
                    "cellIds": ["a"],
                    "cells": [{"id": "a", "code": "x = 1"}],
                },
            },
            {"type": "text", "text": "Inspect x"},
        ],
    }
    tool_result = {
        "id": "assistant-tool",
        "role": "assistant",
        "parts": [
            {
                "type": "tool-read_cell",
                "toolCallId": "read-1",
                "state": "output-available",
                "input": {"cell_id": "a"},
                "output": {"code": "x = 1"},
            }
        ],
    }
    followup = {
        "id": "user-2",
        "role": "user",
        "parts": [
            {
                "type": "data-marimo-notebook",
                "data": {
                    "sessionId": "session-2",
                    "cells": [{"id": "a", "code": "x = 2"}],
                },
            },
            {"type": "text", "text": "Inspect the updated x"},
        ],
    }
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(respond)
    ) as client:
        sdk = AsyncAnthropic(api_key="test-key", http_client=client)
        with patch.object(
            AnthropicProvider,
            "create_provider",
            return_value=PydanticAnthropic(anthropic_client=sdk),
        ):
            provider = AnthropicProvider(
                "claude-sonnet-4-5",
                AnyProviderConfig(api_key="test-key", base_url=None),
            )
        for history in (
            [initial],
            [initial],
            [initial, tool_result],
            [
                initial,
                tool_result,
                {
                    "id": "answer",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "Done"}],
                },
                followup,
            ],
        ):
            agent = provider.create_agent(
                name="chat",
                max_tokens=1024,
                enable_capabilities=False,
                tools=[
                    ToolDefinition(
                        name="read_cell",
                        description="Read a notebook cell.",
                        parameters={
                            "type": "object",
                            "properties": {"cell_id": {"type": "string"}},
                        },
                        source="backend",
                        mode=["ask", "agent"],
                    )
                ],
                system_prompt=get_chat_system_prompt(
                    custom_rules=None, mode=mode
                ),
            )
            # Restored UI history goes through the same conversion as streaming chat.
            restored = json.loads(json.dumps(history))
            result = await agent.run(
                message_history=VercelAIAdapter.load_messages(
                    provider.convert_messages(restored)
                ),
                model_settings={"thinking": False},
            )

            assert result.usage.cache_read_tokens == 100
            assert result.usage.cache_write_tokens == 20

    first, retry, continuation, updated = requests
    assert retry == first
    assert first["tools"] == continuation["tools"] == updated["tools"]
    assert first["tools"][-1]["cache_control"] == {
        "type": "ephemeral",
        "ttl": "5m",
    }
    assert first["system"] == continuation["system"] == updated["system"]
    assert "session-1" not in json.dumps(first["system"])
    assert first["system"][-1]["cache_control"] == {
        "type": "ephemeral",
        "ttl": "5m",
    }
    for request in requests:
        assert request["cache_control"] == {"type": "ephemeral", "ttl": "5m"}
    assert continuation["messages"][:1] == first["messages"]
    assert (
        updated["messages"][: len(continuation["messages"])]
        == continuation["messages"]
    )
    assert "x = 2" in json.dumps(updated["messages"][-1])
    assert "x = 1" not in json.dumps(updated["messages"][-1])
