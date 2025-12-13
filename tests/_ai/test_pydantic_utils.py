# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pydantic_ai", reason="pydantic_ai not installed")

from marimo._ai._pydantic_ai_utils import (
    convert_to_pydantic_messages,
    create_simple_prompt,
    form_toolsets,
    generate_id,
)
from marimo._server.ai.tools.types import ToolDefinition


class TestGenerateId:
    def test_generate_id_with_prefix(self):
        result = generate_id("test")
        assert result.startswith("test_")
        # UUID hex is 32 characters
        assert len(result) == len("test_") + 32

    def test_generate_id_returns_unique_values(self):
        ids = [generate_id("prefix") for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_id_with_empty_prefix(self):
        result = generate_id("")
        assert result.startswith("_")


class TestFormToolsets:
    def test_form_toolsets_empty_list(self):
        tool_invoker = AsyncMock()
        toolset = form_toolsets([], tool_invoker)
        assert toolset is not None

    def test_form_toolsets_with_backend_tool(self):
        tool_invoker = AsyncMock()
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            source="backend",
            mode=["manual"],
        )
        toolset = form_toolsets([tool], tool_invoker)
        assert toolset is not None

    def test_form_toolsets_with_frontend_tool(self):
        tool_invoker = AsyncMock()
        tool = ToolDefinition(
            name="frontend_tool",
            description="A frontend tool",
            parameters={"type": "object", "properties": {}},
            source="frontend",
            mode=["manual"],
        )
        toolset = form_toolsets([tool], tool_invoker)
        assert toolset is not None

    def test_form_toolsets_with_multiple_tools(self):
        tool_invoker = AsyncMock()
        tools = [
            ToolDefinition(
                name="backend_tool",
                description="A backend tool",
                parameters={"type": "object", "properties": {}},
                source="backend",
                mode=["manual"],
            ),
            ToolDefinition(
                name="frontend_tool",
                description="A frontend tool",
                parameters={"type": "object", "properties": {}},
                source="frontend",
                mode=["manual"],
            ),
            ToolDefinition(
                name="mcp_tool",
                description="An MCP tool",
                parameters={"type": "object", "properties": {}},
                source="mcp",
                mode=["manual"],
            ),
        ]
        toolset = form_toolsets(tools, tool_invoker)
        assert toolset is not None

    async def test_backend_tool_invokes_tool_invoker(self):
        @dataclass
        class MockResult:
            value: str

        tool_invoker = AsyncMock(return_value=MockResult(value="result"))
        tool = ToolDefinition(
            name="backend_tool",
            description="A backend tool",
            parameters={"type": "object", "properties": {}},
            source="backend",
            mode=["manual"],
        )
        toolset = form_toolsets([tool], tool_invoker)

        tools = toolset.tools
        assert len(tools) == 1
        assert "backend_tool" in tools
        backend_tool = tools["backend_tool"]
        assert backend_tool.name == "backend_tool"
        assert backend_tool.description == "A backend tool"

        # Actually call the tool function
        result = await backend_tool.function(arg1="test", arg2=123)  # type: ignore[call-arg]

        # Verify tool_invoker was called with correct arguments
        tool_invoker.assert_called_once_with(
            "backend_tool", {"arg1": "test", "arg2": 123}
        )
        # Verify result is converted to dict via asdict
        assert result == {"value": "result"}

    async def test_frontend_tool_raises_call_deferred(self):
        from pydantic_ai import CallDeferred

        tool_invoker = AsyncMock()
        tool = ToolDefinition(
            name="frontend_tool",
            description="A frontend tool",
            parameters={"type": "object", "properties": {}},
            source="frontend",
            mode=["manual"],
        )
        toolset = form_toolsets([tool], tool_invoker)

        tools = toolset.tools
        assert len(tools) == 1
        assert "frontend_tool" in tools
        frontend_tool = tools["frontend_tool"]
        assert frontend_tool.name == "frontend_tool"
        assert frontend_tool.description == "A frontend tool"

        # Call the tool function and verify it raises CallDeferred
        with pytest.raises(CallDeferred) as exc_info:
            await frontend_tool.function(arg="value")  # type: ignore[call-arg]

        # Verify CallDeferred has correct metadata
        assert exc_info.value.metadata == {
            "source": "frontend",
            "tool_name": "frontend_tool",
            "kwargs": {"arg": "value"},
        }
        # Verify tool_invoker was NOT called for frontend tools
        tool_invoker.assert_not_called()


class TestConvertToPydanticMessages:
    def test_convert_empty_messages(self):
        result = convert_to_pydantic_messages([])
        assert result == []

    def test_convert_message_with_message_id(self):
        from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

        messages = [
            {
                "messageId": "msg_123",
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert len(result) == 1
        assert result[0].id == "msg_123"
        assert result[0].role == "user"
        assert result[0].parts == [
            TextUIPart(
                type="text", text="Hello", state=None, provider_metadata=None
            )
        ]

    def test_convert_message_with_id(self):
        messages = [
            {
                "id": "id_456",
                "role": "assistant",
                "parts": [{"type": "text", "text": "Hi there"}],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert len(result) == 1
        assert result[0].id == "id_456"
        assert result[0].role == "assistant"

    def test_convert_message_generates_id_when_missing(self):
        messages = [
            {
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert len(result) == 1
        assert result[0].id.startswith("message_")

    def test_convert_message_prefers_message_id_over_id(self):
        messages = [
            {
                "messageId": "message_id_value",
                "id": "id_value",
                "role": "user",
                "parts": [],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert result[0].id == "message_id_value"

    def test_convert_message_defaults_role_to_assistant(self):
        messages = [
            {
                "id": "test_id",
                "parts": [],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert result[0].role == "assistant"

    def test_convert_message_defaults_parts_to_empty_list(self):
        messages = [
            {
                "id": "test_id",
                "role": "user",
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert result[0].parts == []

    def test_convert_message_with_metadata(self):
        messages = [
            {
                "id": "test_id",
                "role": "user",
                "parts": [],
                "metadata": {"key": "value"},
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert result[0].metadata == {"key": "value"}

    def test_convert_message_without_metadata(self):
        messages = [
            {
                "id": "test_id",
                "role": "user",
                "parts": [],
            }
        ]
        result = convert_to_pydantic_messages(messages)
        assert result[0].metadata is None

    def test_convert_multiple_messages(self):
        messages = [
            {
                "messageId": "msg_1",
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "parts": [{"type": "text", "text": "Hi!"}],
            },
            {
                "role": "user",
                "parts": [{"type": "text", "text": "How are you?"}],
            },
        ]
        result = convert_to_pydantic_messages(messages)
        assert len(result) == 3
        assert result[0].id == "msg_1"
        assert result[1].id == "msg_2"
        assert result[2].id.startswith("message_")


class TestCreateSimplePrompt:
    def test_create_simple_prompt(self):
        from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

        result = create_simple_prompt("Hello, world!")
        assert result.id.startswith("message_")
        assert result.role == "user"
        assert result.parts == [TextUIPart(type="text", text="Hello, world!")]

    def test_create_simple_prompt_with_empty_text(self):
        result = create_simple_prompt("")
        assert result.id.startswith("message_")
        assert result.role == "user"
        assert result.parts == []
