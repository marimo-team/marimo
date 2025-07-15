from __future__ import annotations

import base64
import json

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
    get_anthropic_messages_from_parts,
    get_google_messages_from_parts,
    get_openai_messages_from_parts,
)
from marimo._ai._types import (
    ChatAttachment,
    ChatMessage,
    ReasoningDetails,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
    ToolInvocationResult,
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

    # Test case 5: ChatMessage with tool invocation part (result state only)
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

    # Test case 6: Existing ChatMessage input (should return as-is)
    existing_message = ChatMessage(
        role="user",
        content="I'm already a ChatMessage object",
        attachments=None,
        parts=None,
    )

    result_existing = from_chat_message_dict(existing_message)

    assert result_existing is existing_message  # Should return the same object


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
    # Test text type
    text = "hello world"
    result = convert_to_ai_sdk_messages(text, "text")
    assert result == f"0:{json.dumps(text)}\n"

    # Test reasoning type
    reasoning = "step by step"
    result = convert_to_ai_sdk_messages(reasoning, "reasoning")
    assert result == f"g:{json.dumps(reasoning)}\n"

    # Test reasoning_signature type
    reasoning_signature = {"signature": "encrypted_signature_string"}
    result = convert_to_ai_sdk_messages(
        reasoning_signature, "reasoning_signature"
    )
    assert result == f"j:{json.dumps(reasoning_signature)}\n"

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


# Tests for helper functions that convert parts to provider-specific formats
def test_get_openai_messages_from_parts_text_only():
    """Test converting TextPart to OpenAI format."""
    parts = [
        TextPart(type="text", text="Hello"),
        TextPart(type="text", text="World"),
    ]

    result = get_openai_messages_from_parts("user", parts)

    assert len(result) == 2
    assert result[0] == {"role": "user", "content": "Hello"}
    assert result[1] == {"role": "user", "content": "World"}


def test_get_openai_messages_from_parts_with_tool_invocation():
    """Test converting ToolInvocationPart to OpenAI format."""
    tool_invocation = ToolInvocationResult(
        state="result",
        tool_call_id="call_123",
        tool_name="weather_tool",
        step=1,
        args={"location": "New York"},
        result={"temperature": "72°F", "condition": "sunny"},
    )

    parts = [
        TextPart(type="text", text="Let me check the weather"),
        ToolInvocationPart(
            type="tool-invocation", tool_invocation=tool_invocation
        ),
    ]

    result = get_openai_messages_from_parts("assistant", parts)

    assert len(result) == 3  # text message, assistant tool call, tool result

    # Check text message
    assert result[0] == {
        "role": "assistant",
        "content": "Let me check the weather",
    }

    # Check assistant tool call message
    assert result[1]["role"] == "assistant"
    assert result[1]["content"] is None
    assert len(result[1]["tool_calls"]) == 1
    tool_call = result[1]["tool_calls"][0]
    assert tool_call["id"] == "call_123"
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "weather_tool"
    assert tool_call["function"]["arguments"] == str({"location": "New York"})

    # Check tool result message
    assert result[2]["role"] == "tool"
    assert result[2]["tool_call_id"] == "call_123"
    assert result[2]["name"] == "weather_tool"
    assert result[2]["content"] == str(
        {"temperature": "72°F", "condition": "sunny"}
    )


def test_get_openai_messages_from_parts_empty():
    """Test converting empty parts list."""
    result = get_openai_messages_from_parts("user", [])
    assert result == []


def test_get_anthropic_messages_from_parts_text_only():
    """Test converting TextPart to Anthropic format."""
    parts = [
        TextPart(type="text", text="Hello"),
        TextPart(type="text", text="World"),
    ]

    result = get_anthropic_messages_from_parts("user", parts)

    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == [
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": "World"},
    ]


def test_get_anthropic_messages_from_parts_with_reasoning():
    """Test converting ReasoningPart to Anthropic thinking format."""
    reasoning_details = [
        ReasoningDetails(
            type="text", text="Step 1: Analyze", signature="sig123"
        )
    ]

    parts = [
        TextPart(type="text", text="Let me think about this"),
        ReasoningPart(
            type="reasoning",
            reasoning="My thinking process here",
            details=reasoning_details,
        ),
    ]

    result = get_anthropic_messages_from_parts("assistant", parts)

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == [
        {"type": "text", "text": "Let me think about this"},
        {
            "type": "thinking",
            "thinking": "My thinking process here",
            "signature": "sig123",
        },
    ]


def test_get_anthropic_messages_from_parts_reasoning_no_signature():
    """Test converting ReasoningPart without signature to Anthropic format."""
    reasoning_details = [
        ReasoningDetails(type="text", text="Step 1", signature=None)
    ]

    parts = [
        ReasoningPart(
            type="reasoning",
            reasoning="Basic reasoning",
            details=reasoning_details,
        ),
    ]

    result = get_anthropic_messages_from_parts("assistant", parts)

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == [
        {
            "type": "thinking",
            "thinking": "Basic reasoning",
            "signature": "",  # Should be empty string when no signature
        },
    ]


def test_get_anthropic_messages_from_parts_reasoning_empty_details():
    """Test converting ReasoningPart with empty details list."""
    parts = [
        ReasoningPart(
            type="reasoning",
            reasoning="Some reasoning",
            details=[],  # Empty details
        ),
    ]

    result = get_anthropic_messages_from_parts("assistant", parts)

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == [
        {
            "type": "thinking",
            "thinking": "Some reasoning",
            "signature": "",  # Should be empty when no details
        },
    ]


def test_get_anthropic_messages_from_parts_with_tool_invocation():
    """Test converting ToolInvocationPart to Anthropic format."""
    tool_invocation = ToolInvocationResult(
        state="result",
        tool_call_id="call_123",
        tool_name="search_tool",
        step=1,
        args={"query": "Python tutorials"},
        result={"results": ["tutorial1", "tutorial2"]},
    )

    parts = [
        TextPart(type="text", text="I'll search for you"),
        ToolInvocationPart(
            type="tool-invocation", tool_invocation=tool_invocation
        ),
    ]

    result = get_anthropic_messages_from_parts("assistant", parts)

    assert (
        len(result) == 2
    )  # One message with tool use, one tool result message

    # Check first message with tool use
    assert result[0]["role"] == "assistant"
    expected_content = [
        {"type": "text", "text": "I'll search for you"},
        {
            "type": "tool_use",
            "id": "call_123",
            "name": "search_tool",
            "input": {"query": "Python tutorials"},
        },
    ]
    assert result[0]["content"] == expected_content

    # Check tool result message
    assert result[1]["role"] == "user"
    assert result[1]["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "call_123",
            "content": str({"results": ["tutorial1", "tutorial2"]}),
        }
    ]


def test_get_anthropic_messages_from_parts_single_text():
    """Test converting single TextPart uses string format instead of array."""
    parts = [TextPart(type="text", text="Single message")]

    result = get_anthropic_messages_from_parts("user", parts)

    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert (
        result[0]["content"] == "Single message"
    )  # Should be string, not array


def test_get_google_messages_from_parts_text_only():
    """Test converting TextPart to Google format."""
    parts = [
        TextPart(type="text", text="Hello"),
        TextPart(type="text", text="Google"),
    ]

    result = get_google_messages_from_parts("user", parts)

    assert len(result) == 2
    assert result[0] == {
        "role": "user",
        "parts": [{"text": "Hello"}],
    }
    assert result[1] == {
        "role": "user",
        "parts": [{"text": "Google"}],
    }


def test_get_google_messages_from_parts_with_reasoning():
    """Test converting ReasoningPart to Google thinking format."""
    reasoning_details = [
        ReasoningDetails(type="text", text="Analysis", signature=None)
    ]

    parts = [
        TextPart(type="text", text="Regular text"),
        ReasoningPart(
            type="reasoning",
            reasoning="Deep thinking process",
            details=reasoning_details,
        ),
    ]

    result = get_google_messages_from_parts("assistant", parts)

    assert len(result) == 2

    # Check text message
    assert result[0] == {
        "role": "model",
        "parts": [{"text": "Regular text"}],
    }

    # Check reasoning message with thought flag
    assert result[1] == {
        "role": "model",
        "parts": [{"text": "Deep thinking process", "thought": True}],
    }


def test_get_google_messages_from_parts_with_tool_invocation():
    """Test converting ToolInvocationPart to Google function call format."""
    tool_invocation = ToolInvocationResult(
        state="result",
        tool_call_id="call_456",
        tool_name="calculator",
        step=1,
        args={"expression": "2 + 2"},
        result={"answer": 4},
    )

    parts = [
        ToolInvocationPart(
            type="tool-invocation", tool_invocation=tool_invocation
        ),
    ]

    result = get_google_messages_from_parts("assistant", parts)

    assert (
        len(result) == 2
    )  # Function call message + function response message

    # Check function call message
    assert result[0]["role"] == "model"
    assert result[0]["parts"] == [
        {
            "function_call": {
                "name": "calculator",
                "args": {"expression": "2 + 2"},
            }
        }
    ]

    # Check function response message
    assert result[1]["role"] == "user"
    assert result[1]["parts"] == [
        {
            "function_response": {
                "name": "calculator",
                "response": {"result": "{'answer': 4}"},
            }
        }
    ]


def test_get_google_messages_from_parts_role_mapping():
    """Test that roles are correctly mapped for Google (user -> user, assistant -> model)."""
    parts = [TextPart(type="text", text="Test message")]

    user_result = get_google_messages_from_parts("user", parts)
    assert user_result[0]["role"] == "user"

    assistant_result = get_google_messages_from_parts("assistant", parts)
    assert assistant_result[0]["role"] == "model"


def test_get_google_messages_from_parts_empty():
    """Test converting empty parts list."""
    result = get_google_messages_from_parts("user", [])
    assert result == []
