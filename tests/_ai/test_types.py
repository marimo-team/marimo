# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

import pytest

from marimo._ai._types import (
    ChatMessage,
    ChatPart,
    FilePart,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
)
from marimo._dependencies.dependencies import DependencyManager


class TestChatMessageCreate:
    """Tests for ChatMessage.create class method."""

    def test_basic_usage_without_validator(self):
        """Test create without part_validator_class."""
        parts: list[Any] = [{"type": "text", "text": "Hello"}]

        message = ChatMessage.create(
            role="user",
            message_id="msg-123",
            content="Hello world",
            parts=parts,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-123",
            content="Hello world",
            parts=[TextPart(type="text", text="Hello")],
        )

    def test_with_empty_parts(self):
        """Test create with empty parts list."""
        message = ChatMessage.create(
            role="assistant",
            message_id="msg-456",
            content="Response",
            parts=[],
        )

        assert message == ChatMessage(
            role="assistant",
            id="msg-456",
            content="Response",
            parts=[],
        )

    def test_with_none_content(self):
        """Test create with None content."""
        parts: list[Any] = [{"type": "text", "text": "Content in parts"}]

        message = ChatMessage.create(
            role="user",
            message_id="msg-789",
            content=None,
            parts=parts,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-789",
            content=None,
            parts=[TextPart(type="text", text="Content in parts")],
        )

    def test_parts_already_correct_type_with_validator(self):
        """Test with parts that are already the correct type."""

        @dataclass
        class MockPart:
            type: Literal["mock"]
            value: str

        existing_part = MockPart(type="mock", value="test")

        message = ChatMessage.create(
            role="user",
            message_id="msg-123",
            content=None,
            parts=[cast(ChatPart, existing_part)],
            part_validator_class=MockPart,
        )

        # The part should be kept as-is since it's already the right type
        assert message == ChatMessage(
            role="user",
            id="msg-123",
            content=None,
            parts=[existing_part],  # type: ignore
        )

    def test_dict_parts_with_dataclass_validator(self):
        """Test converting dict parts using a dataclass validator."""
        dict_part: dict[str, str] = {"type": "text", "text": "Hello from dict"}

        message = ChatMessage.create(
            role="user",
            message_id="msg-123",
            content=None,
            parts=[cast(ChatPart, dict_part)],
            part_validator_class=TextPart,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-123",
            content=None,
            parts=[TextPart(type="text", text="Hello from dict")],
        )

    def test_mixed_parts_with_validator(self):
        """Test with a mix of already-typed and dict parts."""

        @dataclass
        class MockPart:
            type: Literal["mock"]
            value: str

        existing_part = MockPart(type="mock", value="existing")
        dict_part: dict[str, str] = {"type": "mock", "value": "from_dict"}

        message = ChatMessage.create(
            role="user",
            message_id="msg-123",
            content=None,
            parts=[cast(ChatPart, existing_part), cast(ChatPart, dict_part)],
            part_validator_class=MockPart,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-123",
            content=None,
            parts=[existing_part, MockPart(type="mock", value="from_dict")],  # type: ignore
        )

    def test_invalid_dict_part_is_skipped(self):
        """Test that invalid dict parts are skipped during validation."""

        @dataclass
        class StrictPart:
            type: Literal["strict"]
            required_field: str

        # This dict is missing required_field
        invalid_dict: dict[str, str] = {"type": "strict"}
        valid_part = StrictPart(type="strict", required_field="valid")

        message = ChatMessage.create(
            role="user",
            message_id="msg-123",
            content=None,
            parts=[cast(ChatPart, valid_part), cast(ChatPart, invalid_dict)],
            part_validator_class=StrictPart,
        )

        # Invalid dict should be skipped, only valid part remains
        assert message.parts is not None
        assert len(message.parts) == 1
        assert message.parts[0] is valid_part

    def test_all_roles(self):
        """Test create with all valid roles."""
        for role in ["user", "assistant", "system"]:
            message = ChatMessage.create(
                role=role,  # type: ignore
                message_id=f"msg-{role}",
                content=f"{role} message",
                parts=[],
            )
            assert message == ChatMessage(
                role=role,  # type: ignore
                id=f"msg-{role}",
                content=f"{role} message",
                parts=[],
            )


class TestChatMessageFromRequestWithPydanticAI:
    """Tests for create with pydantic-ai types."""

    @pytest.mark.skipif(
        not DependencyManager.pydantic_ai.has(),
        reason="pydantic-ai is not installed",
    )
    def test_with_ui_message_part_validator(self):
        """Test create with UIMessagePart from pydantic-ai."""
        from pydantic_ai.ui.vercel_ai.request_types import (
            TextUIPart,
            UIMessagePart,
        )

        dict_part: dict[str, str] = {
            "type": "text",
            "text": "Hello pydantic-ai",
        }

        message = ChatMessage.create(
            role="user",
            message_id="msg-pydantic",
            content=None,
            parts=[cast(ChatPart, dict_part)],
            part_validator_class=UIMessagePart,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-pydantic",
            content=None,
            parts=cast(
                Any, [TextUIPart(type="text", text="Hello pydantic-ai")]
            ),
        )

    @pytest.mark.skipif(
        not DependencyManager.pydantic_ai.has(),
        reason="pydantic-ai is not installed",
    )
    def test_with_existing_ui_message_part(self):
        """Test that existing UIMessagePart instances are kept as-is."""
        from pydantic_ai.ui.vercel_ai.request_types import (
            TextUIPart,
            UIMessagePart,
        )

        existing_part = TextUIPart(type="text", text="Already typed")

        message = ChatMessage.create(
            role="assistant",
            message_id="msg-existing",
            content=None,
            parts=[cast(ChatPart, existing_part)],
            part_validator_class=UIMessagePart,
        )

        # Check identity - the same object should be kept
        assert message.parts is not None
        assert len(message.parts) == 1
        assert message.parts[0] is existing_part

    @pytest.mark.skipif(
        not DependencyManager.pydantic_ai.has(),
        reason="pydantic-ai is not installed",
    )
    def test_with_multiple_ui_part_types(self):
        """Test create with multiple UI part types."""
        from pydantic_ai.ui.vercel_ai.request_types import (
            TextUIPart,
            UIMessagePart,
        )

        parts: list[dict[str, str]] = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"},
        ]

        message = ChatMessage.create(
            role="user",
            message_id="msg-multi",
            content=None,
            parts=cast(Any, parts),
            part_validator_class=UIMessagePart,
        )

        assert message == ChatMessage(
            role="user",
            id="msg-multi",
            content=None,
            parts=cast(
                Any,
                [
                    TextUIPart(type="text", text="First part"),
                    TextUIPart(type="text", text="Second part"),
                ],
            ),
        )

    @pytest.mark.skipif(
        not DependencyManager.pydantic_ai.has(),
        reason="pydantic-ai is not installed",
    )
    def test_with_reasoning_ui_part(self):
        """Test create with reasoning UI part."""
        from pydantic_ai.ui.vercel_ai.request_types import (
            ReasoningUIPart,
            UIMessagePart,
        )

        parts: list[dict[str, str]] = [
            {"type": "reasoning", "text": "Let me think about this..."},
        ]

        message = ChatMessage.create(
            role="assistant",
            message_id="msg-reasoning",
            content=None,
            parts=cast(Any, parts),
            part_validator_class=UIMessagePart,
        )

        assert message == ChatMessage(
            role="assistant",
            id="msg-reasoning",
            content=None,
            parts=cast(
                Any,
                [
                    ReasoningUIPart(
                        type="reasoning", text="Let me think about this..."
                    )
                ],
            ),
        )


class TestChatMessagePostInit:
    """Tests for ChatMessage.__post_init__ part conversion."""

    def test_converts_text_part_dict(self):
        """Test that text part dicts are converted to TextPart."""
        message = ChatMessage(
            role="user",
            content="Hello",
            parts=[cast(ChatPart, {"type": "text", "text": "Part text"})],
        )

        assert message == ChatMessage(
            role="user",
            content="Hello",
            parts=[TextPart(type="text", text="Part text")],
        )

    def test_converts_reasoning_part_dict(self):
        """Test that reasoning part dicts are converted to ReasoningPart."""
        message = ChatMessage(
            role="assistant",
            content=None,
            parts=[
                cast(ChatPart, {"type": "reasoning", "text": "Thinking..."})
            ],
        )

        assert message == ChatMessage(
            role="assistant",
            content=None,
            parts=[ReasoningPart(type="reasoning", text="Thinking...")],
        )

    def test_converts_file_part_dict(self):
        """Test that file part dicts are converted to FilePart."""
        message = ChatMessage(
            role="user",
            content=None,
            parts=[
                cast(
                    ChatPart,
                    {
                        "type": "file",
                        "media_type": "image/png",
                        "url": "data:image/png;base64,abc123",
                    },
                ),
            ],
        )

        assert message == ChatMessage(
            role="user",
            content=None,
            parts=[
                FilePart(
                    type="file",
                    media_type="image/png",
                    url="data:image/png;base64,abc123",
                )
            ],
        )

    def test_converts_tool_invocation_part_dict(self):
        """Test that tool invocation part dicts are converted."""
        message = ChatMessage(
            role="assistant",
            content=None,
            parts=cast(
                Any,
                [
                    {
                        "type": "tool-call",
                        "tool_call_id": "call-123",
                        "state": "output-available",
                        "input": {"query": "test"},
                        "output": {"result": "success"},
                    }
                ],
            ),
        )

        assert message == ChatMessage(
            role="assistant",
            content=None,
            parts=[
                ToolInvocationPart(
                    type="tool-call",
                    tool_call_id="call-123",
                    state="output-available",
                    input={"query": "test"},
                    output={"result": "success"},
                )
            ],
        )

    def test_keeps_already_typed_parts(self):
        """Test that already-typed parts are kept as-is."""
        text_part = TextPart(type="text", text="Already typed")
        message = ChatMessage(
            role="user",
            content="Hello",
            parts=[text_part],
        )

        # Check identity - the same object should be kept
        assert message.parts is not None
        assert len(message.parts) == 1
        assert message.parts[0] is text_part

    def test_handles_invalid_parts_gracefully(self):
        """Test that invalid parts are dropped gracefully."""
        message = ChatMessage(
            role="user",
            content="Hello",
            parts=cast(
                Any,
                [
                    {"type": "text", "text": "Valid"},
                    {"type": "unknown_type", "data": "invalid"},
                ],
            ),
        )

        # Valid part should be kept, invalid should be dropped
        assert message == ChatMessage(
            role="user",
            content="Hello",
            parts=[TextPart(type="text", text="Valid")],
        )

    def test_with_none_parts(self):
        """Test that None parts is handled."""
        message = ChatMessage(role="user", content="Hello", parts=[])
        assert message == ChatMessage(role="user", content="Hello", parts=[])

    def test_with_empty_parts(self):
        """Test that empty parts list stays empty."""
        message = ChatMessage(role="user", content="Hello", parts=[])

        assert message == ChatMessage(role="user", content="Hello", parts=[])
