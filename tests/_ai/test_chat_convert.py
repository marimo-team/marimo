from __future__ import annotations

import base64

import pytest

from marimo._ai._convert import (
    convert_to_ai_sdk_messages,
    convert_to_anthropic_messages,
    convert_to_anthropic_tools,
    convert_to_google_messages,
    convert_to_google_tools,
    convert_to_groq_messages,
    convert_to_openai_messages,
    convert_to_openai_tools,
)
from marimo._ai._types import (
    ChatAttachment,
    ChatMessage,
)
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict
from marimo._server.ai.tools import Tool


@pytest.fixture
def sample_messages() -> list[ChatMessage]:
    return [
        ChatMessage(
            role="user",
            content="Hello, I have a question.",
            attachments=[
                ChatAttachment(
                    name="image.png",
                    content_type="image/png",
                    url=f"data:image/png;base64,{base64.b64encode(b'hello')}",
                ),
                ChatAttachment(
                    name="text.txt",
                    content_type="text/plain",
                    url="data:text/csv;base64,QQoxCjIKMwo=",
                ),
            ],
        ),
        ChatMessage(
            role="assistant",
            content="Sure, I'd be happy to help. What's your question?",
            attachments=[],
        ),
    ]


def test_convert_to_openai_messages(sample_messages: list[ChatMessage]):
    result = convert_to_openai_messages(sample_messages)

    assert len(result) == 2

    # Check user message
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) == 3
    assert result[0]["content"][0] == {
        "type": "text",
        "text": "Hello, I have a question.",
    }
    assert result[0]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,b'aGVsbG8='"},
    }
    assert result[0]["content"][2] == {
        "type": "text",
        "text": "A\n1\n2\n3\n",
    }

    # Check assistant message
    assert result[1]["role"] == "assistant"
    assert (
        result[1]["content"]
        == "Sure, I'd be happy to help. What's your question?"
    )


def test_convert_to_anthropic_messages(sample_messages: list[ChatMessage]):
    result = convert_to_anthropic_messages(sample_messages)

    assert len(result) == 2

    # Check user message
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) == 3
    assert result[0]["content"][0] == {
        "type": "text",
        "text": "Hello, I have a question.",
    }
    assert result[0]["content"][1] == {
        "type": "image",
        "source": {
            "data": "b'aGVsbG8='",
            "media_type": "image/png",
            "type": "base64",
        },
    }
    assert result[0]["content"][2] == {
        "type": "text",
        "text": "A\n1\n2\n3\n",
    }

    # Check assistant message
    assert result[1]["role"] == "assistant"
    assert (
        result[1]["content"]
        == "Sure, I'd be happy to help. What's your question?"
    )


def test_convert_to_google_messages(sample_messages: list[ChatMessage]):
    result = convert_to_google_messages(sample_messages)

    assert len(result) == 2

    # Check user message
    assert result[0]["role"] == "user"
    assert result[0]["parts"] == [
        {"text": "Hello, I have a question."},
        {
            "inline_data": {
                "data": b"m\xa1\x95\xb1\xb1\xbc",
                "mime_type": "image/png",
            }
        },
        {
            "inline_data": {
                "data": b"A\n1\n2\n3\n",
                "mime_type": "text/plain",
            }
        },
    ]

    # Check assistant message
    assert result[1]["role"] == "model"
    assert result[1]["parts"] == [
        {"text": "Sure, I'd be happy to help. What's your question?"}
    ]


def test_convert_to_groq_messages(sample_messages: list[ChatMessage]):
    result = convert_to_groq_messages(sample_messages)

    assert len(result) == 2

    # Check user message with text attachment
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Hello, I have a question.\nA\n1\n2\n3\n"

    # Check assistant message
    assert result[1]["role"] == "assistant"
    assert (
        result[1]["content"]
        == "Sure, I'd be happy to help. What's your question?"
    )


def test_empty_messages():
    empty_messages = []
    assert convert_to_openai_messages(empty_messages) == []
    assert convert_to_anthropic_messages(empty_messages) == []
    assert convert_to_google_messages(empty_messages) == []
    assert convert_to_groq_messages(empty_messages) == []


def test_message_without_attachments():
    messages = [
        ChatMessage(
            role="user", content="Just a simple message", attachments=[]
        )
    ]

    openai_result = convert_to_openai_messages(messages)
    assert len(openai_result) == 1
    assert openai_result[0]["role"] == "user"
    assert openai_result[0]["content"] == "Just a simple message"

    anthropic_result = convert_to_anthropic_messages(messages)
    assert len(anthropic_result) == 1
    assert anthropic_result[0]["role"] == "user"
    assert anthropic_result[0]["content"] == "Just a simple message"

    google_result = convert_to_google_messages(messages)
    assert len(google_result) == 1
    assert google_result[0]["role"] == "user"
    assert google_result[0]["parts"] == [{"text": "Just a simple message"}]

    groq_result = convert_to_groq_messages(messages)
    assert len(groq_result) == 1
    assert groq_result[0]["role"] == "user"
    assert groq_result[0]["content"] == "Just a simple message"


def test_from_chat_message_dict():
    # Test case 1: ChatMessage with attachments
    message_dict = {
        "role": "user",
        "content": "Hello, this is a test message.",
        "attachments": [
            {
                "name": "test.png",
                "content_type": "image/png",
                "url": "http://example.com/test.png",
            }
        ],
    }

    result = from_chat_message_dict(message_dict)

    assert isinstance(result, ChatMessage)
    assert result.role == "user"
    assert result.content == "Hello, this is a test message."
    assert len(result.attachments) == 1
    assert isinstance(result.attachments[0], ChatAttachment)
    assert result.attachments[0].name == "test.png"
    assert result.attachments[0].content_type == "image/png"
    assert result.attachments[0].url == "http://example.com/test.png"

    # Test case 2: ChatMessage without attachments
    message_dict_no_attachments = {
        "role": "assistant",
        "content": "This is a response without attachments.",
    }

    result_no_attachments = from_chat_message_dict(message_dict_no_attachments)

    assert isinstance(result_no_attachments, ChatMessage)
    assert result_no_attachments.role == "assistant"
    assert (
        result_no_attachments.content
        == "This is a response without attachments."
    )
    assert result_no_attachments.attachments is None

    # Test case 3: ChatMessage with parts
    message_dict_with_parts = {
        "role": "assistant",
        "content": "Here's my response with reasoning.",
        "parts": [
            {"type": "text", "text": "This is a text part"},
            {"type": "reasoning", "reasoning": "This is my reasoning process"},
        ],
    }

    result_with_parts = from_chat_message_dict(message_dict_with_parts)

    assert isinstance(result_with_parts, ChatMessage)
    assert result_with_parts.role == "assistant"
    assert result_with_parts.content == "Here's my response with reasoning."
    assert len(result_with_parts.parts) == 2
    assert result_with_parts.parts[0].type == "text"
    assert result_with_parts.parts[0].text == "This is a text part"
    assert result_with_parts.parts[1].type == "reasoning"
    assert (
        result_with_parts.parts[1].reasoning == "This is my reasoning process"
    )

    # Test case 4: ChatMessage with both attachments and parts
    message_dict_full = {
        "role": "user",
        "content": "Complex message with everything.",
        "attachments": [
            {
                "name": "doc.pdf",
                "content_type": "application/pdf",
                "url": "http://example.com/doc.pdf",
            }
        ],
        "parts": [{"type": "text", "text": "Additional text content"}],
    }

    result_full = from_chat_message_dict(message_dict_full)

    assert isinstance(result_full, ChatMessage)
    assert result_full.role == "user"
    assert result_full.content == "Complex message with everything."
    assert len(result_full.attachments) == 1
    assert result_full.attachments[0].name == "doc.pdf"
    assert len(result_full.parts) == 1
    assert result_full.parts[0].type == "text"
    assert result_full.parts[0].text == "Additional text content"

    # Test case 5: ChatMessage with tool invocation part (call state)
    message_dict_tool_call = {
        "role": "assistant",
        "content": "I'll call a tool for you.",
        "parts": [
            {
                "type": "tool-invocation",
                "tool_invocation": {
                    "state": "call",
                    "tool_call_id": "call_123",
                    "tool_name": "weather_tool",
                    "step": 1,
                    "args": {"location": "New York"},
                },
            }
        ],
    }

    result_tool_call = from_chat_message_dict(message_dict_tool_call)

    assert isinstance(result_tool_call, ChatMessage)
    assert result_tool_call.role == "assistant"
    assert result_tool_call.content == "I'll call a tool for you."
    assert len(result_tool_call.parts) == 1
    assert result_tool_call.parts[0].type == "tool-invocation"
    assert result_tool_call.parts[0].tool_invocation.state == "call"
    assert result_tool_call.parts[0].tool_invocation.tool_call_id == "call_123"
    assert (
        result_tool_call.parts[0].tool_invocation.tool_name == "weather_tool"
    )
    assert result_tool_call.parts[0].tool_invocation.step == 1
    assert result_tool_call.parts[0].tool_invocation.args == {
        "location": "New York"
    }

    # Test case 6: ChatMessage with tool invocation part (result state)
    message_dict_tool_result = {
        "role": "assistant",
        "content": "Here's the tool result.",
        "parts": [
            {
                "type": "tool-invocation",
                "tool_invocation": {
                    "state": "result",
                    "result": {"temperature": "72°F", "condition": "sunny"},
                    "tool_call_id": "call_123",
                    "tool_name": "weather_tool",
                    "step": 1,
                    "args": {"location": "New York"},
                },
            }
        ],
    }

    result_tool_result = from_chat_message_dict(message_dict_tool_result)

    assert isinstance(result_tool_result, ChatMessage)
    assert result_tool_result.role == "assistant"
    assert result_tool_result.content == "Here's the tool result."
    assert len(result_tool_result.parts) == 1
    assert result_tool_result.parts[0].type == "tool-invocation"
    assert result_tool_result.parts[0].tool_invocation.state == "result"
    assert result_tool_result.parts[0].tool_invocation.result == {
        "temperature": "72°F",
        "condition": "sunny",
    }
    assert (
        result_tool_result.parts[0].tool_invocation.tool_call_id == "call_123"
    )
    assert (
        result_tool_result.parts[0].tool_invocation.tool_name == "weather_tool"
    )
    assert result_tool_result.parts[0].tool_invocation.step == 1
    assert result_tool_result.parts[0].tool_invocation.args == {
        "location": "New York"
    }

    # Test case 7: ChatMessage with mixed parts (text, reasoning, and tool invocation)
    message_dict_mixed = {
        "role": "assistant",
        "content": "Complex response with multiple part types.",
        "parts": [
            {"type": "text", "text": "First, let me explain."},
            {
                "type": "reasoning",
                "reasoning": "I need to call a tool because...",
            },
            {
                "type": "tool-invocation",
                "tool_invocation": {
                    "state": "partial-call",
                    "tool_call_id": "call_456",
                    "tool_name": "calculator",
                    "step": 2,
                    "args": {"expression": "2 + 2"},
                },
            },
        ],
    }

    result_mixed = from_chat_message_dict(message_dict_mixed)

    assert isinstance(result_mixed, ChatMessage)
    assert result_mixed.role == "assistant"
    assert result_mixed.content == "Complex response with multiple part types."
    assert len(result_mixed.parts) == 3

    # Check text part
    assert result_mixed.parts[0].type == "text"
    assert result_mixed.parts[0].text == "First, let me explain."

    # Check reasoning part
    assert result_mixed.parts[1].type == "reasoning"
    assert (
        result_mixed.parts[1].reasoning == "I need to call a tool because..."
    )

    # Check tool invocation part
    assert result_mixed.parts[2].type == "tool-invocation"
    assert result_mixed.parts[2].tool_invocation.state == "partial-call"
    assert result_mixed.parts[2].tool_invocation.tool_call_id == "call_456"
    assert result_mixed.parts[2].tool_invocation.tool_name == "calculator"
    assert result_mixed.parts[2].tool_invocation.step == 2
    assert result_mixed.parts[2].tool_invocation.args == {
        "expression": "2 + 2"
    }

    # Test case 8: Input is already a ChatMessage
    existing_chat_message = ChatMessage(
        role="system", content="System message", attachments=None, parts=None
    )

    result_existing = from_chat_message_dict(existing_chat_message)

    assert result_existing is existing_chat_message


@pytest.fixture
def sample_tools():
    return [
        Tool(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
            },
            source="mcp",
            mode=["manual"],
        )
    ]


def test_convert_to_openai_tools(sample_tools):
    result = convert_to_openai_tools(sample_tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "test_tool"
    assert result[0]["function"]["description"] == "A test tool"
    assert result[0]["function"]["parameters"] == {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
    }


def test_convert_to_anthropic_tools(sample_tools):
    result = convert_to_anthropic_tools(sample_tools)
    assert len(result) == 1
    assert result[0]["name"] == "test_tool"
    assert result[0]["description"] == "A test tool"
    assert result[0]["input_schema"] == {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
    }


def test_convert_to_google_tools(sample_tools):
    result = convert_to_google_tools(sample_tools)
    assert len(result) == 1
    assert "function_declarations" in result[0]
    assert result[0]["function_declarations"][0]["name"] == "test_tool"
    assert (
        result[0]["function_declarations"][0]["description"] == "A test tool"
    )
    assert result[0]["function_declarations"][0]["parameters"] == {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
    }


def test_convert_to_ai_sdk_messages():
    import json

    # Test text type
    text = "hello world"
    result = convert_to_ai_sdk_messages(text, "text")
    assert result == f"0:{json.dumps(text)}\n"

    # Test reasoning type
    reasoning = "step by step"
    result = convert_to_ai_sdk_messages(reasoning, "reasoning")
    assert result == f"g:{json.dumps(reasoning)}\n"

    # Test tool_call_start type
    tool_call_start = {"toolCallId": "123", "toolName": "test_tool"}
    result = convert_to_ai_sdk_messages(tool_call_start, "tool_call_start")
    assert result == f"b:{json.dumps(tool_call_start)}\n"

    # Test tool_call_delta type
    tool_call_delta = {"toolCallId": "123", "argsTextDelta": "partial args"}
    result = convert_to_ai_sdk_messages(tool_call_delta, "tool_call_delta")
    assert result == f"c:{json.dumps(tool_call_delta)}\n"

    # Test tool_call_end type
    tool_call_end = {
        "toolCallId": "123",
        "toolName": "test_tool",
        "args": {"param": "value"},
    }
    result = convert_to_ai_sdk_messages(tool_call_end, "tool_call_end")
    assert result == f"9:{json.dumps(tool_call_end)}\n"

    # Test tool_result type
    tool_result = {"toolCallId": "123", "result": "success"}
    result = convert_to_ai_sdk_messages(tool_result, "tool_result")
    assert result == f"a:{json.dumps(tool_result)}\n"

    # Test finish_reason type with "tool_calls"
    result = convert_to_ai_sdk_messages("tool_calls", "finish_reason")
    expected = 'd:{"finishReason": "tool_calls", "usage": {"promptTokens": 0, "completionTokens": 0}}\n'
    assert result == expected

    # Test finish_reason type with "stop"
    result = convert_to_ai_sdk_messages("stop", "finish_reason")
    expected = 'd:{"finishReason": "stop", "usage": {"promptTokens": 0, "completionTokens": 0}}\n'
    assert result == expected

    # Test unknown type defaults to text
    result = convert_to_ai_sdk_messages("fallback", "unknown")
    assert result == f"0:{json.dumps('fallback')}\n"
