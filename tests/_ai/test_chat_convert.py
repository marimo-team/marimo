from __future__ import annotations

import base64
import json
from copy import deepcopy

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
    get_anthropic_parts_from_chat_parts,
    get_google_messages_from_parts,
    get_openai_messages_from_parts,
)
from marimo._ai._types import (
    ChatMessage,
    FilePart,
    ReasoningDetails,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
)
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict
from marimo._server.ai.tools.types import Tool


@pytest.fixture
def sample_messages() -> list[ChatMessage]:
    return [
        ChatMessage(
            role="user",
            content="Hello, I have a question.",
            parts=[
                TextPart(type="text", text="Hello, I have a question."),
                FilePart(
                    type="file",
                    media_type="image/png",
                    filename="image.png",
                    url=f"data:image/png;base64,{base64.b64encode(b'hello')}",
                ),
                TextPart(type="text", text="A\n1\n2\n3\n"),
            ],
        ),
        ChatMessage(
            role="assistant",
            content="Sure, I'd be happy to help. What's your question?",
            parts=[
                TextPart(
                    type="text",
                    text="Sure, I'd be happy to help. What's your question?",
                ),
            ],
        ),
    ]


def test_convert_to_openai_messages(
    sample_messages: list[ChatMessage],
):
    result = convert_to_openai_messages(sample_messages)
    assert result == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello, I have a question."},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,b'aGVsbG8='"},
                },
                {"type": "text", "text": "A\n1\n2\n3\n"},
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Sure, I'd be happy to help. What's your question?",
                }
            ],
        },
    ]


def test_convert_to_openai_messages_with_parts():
    sample_messages = [
        ChatMessage(
            role="user",
            content="Message with parts and attachments",
            parts=[
                TextPart(
                    type="text", text="Message with parts and attachments"
                ),
                ReasoningPart(
                    type="reasoning",
                    reasoning="Deep thinking process",
                    details=[
                        ReasoningDetails(
                            type="text", text="Analysis", signature=None
                        )
                    ],
                ),
                ToolInvocationPart(
                    type="tool-calculator",
                    tool_call_id="call_123",
                    state="output-available",
                    input={"expression": "2 + 2"},
                    output={"answer": 4},
                ),
                FilePart(
                    type="file",
                    media_type="image/png",
                    filename="image.png",
                    url=f"data:image/png;base64,{base64.b64encode(b'hello')}",
                ),
            ],
        ),
    ]
    result = convert_to_openai_messages(sample_messages)
    assert result == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Message with parts and attachments"},
                {
                    "type": "reasoning",
                    "reasoning": "Deep thinking process",
                    "details": [
                        {"type": "text", "text": "Analysis", "signature": None}
                    ],
                },
                {
                    "type": "tool-calculator",
                    "tool_call_id": "call_123",
                    "state": "output-available",
                    "input": {"expression": "2 + 2"},
                    "output": {"answer": 4},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,b'aGVsbG8='"},
                },
            ],
        }
    ]


def test_convert_to_anthropic_messages(
    sample_messages: list[ChatMessage],
):
    result = convert_to_anthropic_messages(sample_messages)
    assert result == [
        # User message
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello, I have a question."},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "b'aGVsbG8='",
                    },
                },
                {"type": "text", "text": "A\n1\n2\n3\n"},
            ],
        },
        # Assistant message
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Sure, I'd be happy to help. What's your question?",
                }
            ],
        },
    ]


def test_convert_to_google_messages(
    sample_messages: list[ChatMessage],
):
    result = convert_to_google_messages(sample_messages)
    assert result == [
        # User message
        {
            "role": "user",
            "parts": [
                {"text": "Hello, I have a question."},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": b"m\xa1\x95\xb1\xb1\xbc",
                    }
                },
                {"text": "A\n1\n2\n3\n"},
            ],
        },
        # Assistant message
        {
            "role": "model",
            "parts": [
                {"text": "Sure, I'd be happy to help. What's your question?"}
            ],
        },
    ]


def test_convert_to_groq_messages(
    sample_messages: list[ChatMessage],
):
    new_messages = deepcopy(sample_messages)
    # replace image file part with text file part
    new_messages[0].parts[1] = FilePart(
        filename="text.txt",
        type="file",
        media_type="text/plain",
        url="data:text/plain;base64,R29vZGJ5ZQ==",
    )
    result = convert_to_groq_messages(new_messages)

    assert result == [
        # User message
        {"role": "user", "content": "Hello, I have a question.\nGoodbye"},
        # Assistant message
        {
            "role": "assistant",
            "content": "Sure, I'd be happy to help. What's your question?",
        },
    ]


def test_empty_messages():
    empty_messages = []
    assert convert_to_openai_messages(empty_messages) == []
    assert convert_to_anthropic_messages(empty_messages) == []
    assert convert_to_google_messages(empty_messages) == []
    assert convert_to_groq_messages(empty_messages) == []


def test_message_without_attachments():
    messages = [
        ChatMessage(
            role="user",
            content="Just a simple message",
            attachments=[],
            parts=[TextPart(type="text", text="Just a simple message")],
        )
    ]

    openai_result = convert_to_openai_messages(messages)
    assert openai_result == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Just a simple message"}],
        }
    ]

    anthropic_result = convert_to_anthropic_messages(messages)
    assert anthropic_result == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Just a simple message"}],
        }
    ]

    google_result = convert_to_google_messages(messages)
    assert google_result == [
        {
            "role": "user",
            "parts": [{"text": "Just a simple message"}],
        }
    ]

    groq_result = convert_to_groq_messages(messages)
    assert groq_result == [
        {"role": "user", "content": "Just a simple message"}
    ]


def test_from_chat_message_dict():
    # Test case 1: ChatMessage with attachments
    message_dict = {
        "role": "user",
        "content": "Hello, this is a test message.",
        "parts": [
            {
                "type": "file",
                "media_type": "image/png",
                "filename": "test.png",
                "url": "http://example.com/test.png",
            }
        ],
    }

    result = from_chat_message_dict(message_dict)
    assert result == ChatMessage(
        role="user",
        content="Hello, this is a test message.",
        attachments=None,
        parts=[
            FilePart(
                type="file",
                media_type="image/png",
                filename="test.png",
                url="http://example.com/test.png",
            )
        ],
    )

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

    # Test case 4: ChatMessage with tool invocation part (result state only)
    message_dict_tool_result = {
        "role": "assistant",
        "content": "Here's the tool result.",
        "parts": [
            {
                "type": "tool-weather_tool",
                "tool_call_id": "call_123",
                "state": "output-available",
                "input": {"location": "New York"},
                "output": {"temperature": "72°F", "condition": "sunny"},
            }
        ],
    }

    result_tool_result = from_chat_message_dict(message_dict_tool_result)

    assert isinstance(result_tool_result, ChatMessage)
    assert result_tool_result.role == "assistant"
    assert result_tool_result.content == "Here's the tool result."
    assert len(result_tool_result.parts) == 1
    assert result_tool_result.parts[0].type == "tool-weather_tool"
    assert result_tool_result.parts[0].state == "output-available"
    assert result_tool_result.parts[0].output == {
        "temperature": "72°F",
        "condition": "sunny",
    }
    assert result_tool_result.parts[0].tool_call_id == "call_123"
    assert result_tool_result.parts[0].tool_name == "weather_tool"
    assert result_tool_result.parts[0].input == {"location": "New York"}

    # Test case 5: Existing ChatMessage input (should return as-is)
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
    # Add some additional parameters in tools, it should be ignored
    sample_tools[0].parameters["maxNumResults"] = 10
    result = convert_to_google_tools(sample_tools)
    assert result == [
        {
            "function_declarations": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {"x": {"type": "integer"}},
                        "required": [],
                    },
                }
            ]
        }
    ]


def test_convert_to_ai_sdk_messages():
    # Test text type
    text = "hello world"
    result = convert_to_ai_sdk_messages(text, "text", text_id="test_text_id")
    expected = f"data: {json.dumps({'type': 'text-delta', 'id': 'test_text_id', 'delta': text})}\n\n"
    assert result == expected

    # Test reasoning type
    reasoning = "step by step"
    result = convert_to_ai_sdk_messages(
        reasoning, "reasoning", text_id="test_reasoning_id"
    )
    expected = f"data: {json.dumps({'type': 'reasoning-delta', 'id': 'test_reasoning_id', 'delta': reasoning})}\n\n"
    assert result == expected

    # Test reasoning_signature type
    reasoning_signature = {"signature": "encrypted_signature_string"}
    result = convert_to_ai_sdk_messages(
        reasoning_signature, "reasoning_signature"
    )
    expected = f"data: {json.dumps({'type': 'data-reasoning-signature', 'data': reasoning_signature})}\n\n"
    assert result == expected

    # Test tool_call_start type
    tool_call_start = {"toolCallId": "123", "toolName": "test_tool"}
    result = convert_to_ai_sdk_messages(tool_call_start, "tool_call_start")
    expected = f"data: {json.dumps({'type': 'tool-input-start', 'toolCallId': '123', 'toolName': 'test_tool'})}\n\n"
    assert result == expected

    # Test tool_call_delta type
    tool_call_delta = {"toolCallId": "123", "inputTextDelta": "partial args"}
    result = convert_to_ai_sdk_messages(tool_call_delta, "tool_call_delta")
    expected = f"data: {json.dumps({'type': 'tool-input-delta', 'toolCallId': '123', 'inputTextDelta': 'partial args'})}\n\n"
    assert result == expected

    # Test tool_call_end type
    tool_call_end = {
        "toolCallId": "123",
        "toolName": "test_tool",
        "input": {"param": "value"},
    }
    result = convert_to_ai_sdk_messages(tool_call_end, "tool_call_end")
    expected_data = {
        "type": "tool-input-available",
        "toolCallId": "123",
        "toolName": "test_tool",
        "input": {"param": "value"},
    }
    expected = f"data: {json.dumps(expected_data)}\n\n"
    assert result == expected

    # Test tool_result type
    tool_result = {"toolCallId": "123", "output": "success"}
    result = convert_to_ai_sdk_messages(tool_result, "tool_result")
    expected = f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': '123', 'output': 'success'})}\n\n"
    assert result == expected

    # Test finish_reason type
    result = convert_to_ai_sdk_messages("tool_calls", "finish_reason")
    expected = f"data: {json.dumps({'type': 'finish'})}\n\n"
    assert result == expected

    # Test finish_reason type with "stop" - same as above
    result = convert_to_ai_sdk_messages("stop", "finish_reason")
    expected = f"data: {json.dumps({'type': 'finish'})}\n\n"
    assert result == expected

    # Test error type
    error_message = "Model not found"
    result = convert_to_ai_sdk_messages(error_message, "error")
    expected = f"data: {json.dumps({'type': 'error', 'errorText': error_message})}\n\n"
    assert result == expected

    # Test text_start type
    result = convert_to_ai_sdk_messages(
        "", "text_start", text_id="test_text_start_id"
    )
    expected = f"data: {json.dumps({'type': 'text-start', 'id': 'test_text_start_id'})}\n\n"
    assert result == expected

    # Test text_end type
    result = convert_to_ai_sdk_messages(
        "", "text_end", text_id="test_text_end_id"
    )
    expected = f"data: {json.dumps({'type': 'text-end', 'id': 'test_text_end_id'})}\n\n"
    assert result == expected

    # Test reasoning_start type
    result = convert_to_ai_sdk_messages(
        "", "reasoning_start", text_id="test_reasoning_start_id"
    )
    expected = f"data: {json.dumps({'type': 'reasoning-start', 'id': 'test_reasoning_start_id'})}\n\n"
    assert result == expected

    # Test reasoning_end type
    result = convert_to_ai_sdk_messages(
        "", "reasoning_end", text_id="test_reasoning_end_id"
    )
    expected = f"data: {json.dumps({'type': 'reasoning-end', 'id': 'test_reasoning_end_id'})}\n\n"
    assert result == expected

    # Test unknown type defaults to text-delta (using type ignore for testing)
    result = convert_to_ai_sdk_messages(
        "fallback", "unknown", text_id="test_fallback_id"
    )  # type: ignore
    expected = f"data: {json.dumps({'type': 'text-delta', 'id': 'test_fallback_id', 'delta': 'fallback'})}\n\n"
    assert result == expected


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
    parts = [
        TextPart(type="text", text="Let me check the weather"),
        ToolInvocationPart(
            type="tool-weather_tool",
            tool_call_id="call_123",
            state="output-available",
            input={"location": "New York"},
            output={"temperature": "72°F", "condition": "sunny"},
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


def test_get_anthropic_parts_from_chat_parts_text_only():
    """Test converting TextPart to Anthropic format."""
    parts = [
        TextPart(type="text", text="Hello"),
        TextPart(type="text", text="World"),
    ]

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": "World"},
    ]


def test_get_anthropic_parts_from_chat_parts_with_reasoning():
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

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [
        {"type": "text", "text": "Let me think about this"},
        {
            "type": "thinking",
            "thinking": "My thinking process here",
            "signature": "sig123",
        },
    ]


def test_get_anthropic_parts_from_chat_parts_reasoning_no_signature():
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

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [
        {
            "type": "thinking",
            "thinking": "Basic reasoning",
            "signature": "",  # Should be empty string when no signature
        }
    ]


def test_get_anthropic_parts_from_empty_reasoning_details_chat_part():
    """Test converting ReasoningPart with empty details list."""
    parts = [
        ReasoningPart(
            type="reasoning",
            reasoning="Some reasoning",
            details=[],  # Empty details
        ),
    ]

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [
        {
            "type": "thinking",
            "thinking": "Some reasoning",
            "signature": "",  # Should be empty when no details
        }
    ]


def test_get_anthropic_parts_from_chat_parts_with_tool_invocation():
    """Test converting ToolInvocationPart to Anthropic format."""
    parts = [
        TextPart(type="text", text="I'll search for you"),
        ToolInvocationPart(
            type="tool-search_tool",
            tool_call_id="call_123",
            state="output-available",
            input={"query": "Python tutorials"},
            output={"results": ["tutorial1", "tutorial2"]},
        ),
    ]

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [
        # Text message
        {"type": "text", "text": "I'll search for you"},
        # Tool use message
        {
            "type": "tool_use",
            "id": "call_123",
            "name": "search_tool",
            "input": {"query": "Python tutorials"},
        },
        # Tool result message
        {
            "tool_use_id": "call_123",
            "type": "tool_result",
            "content": [
                {
                    "type": "text",
                    "text": "{'results': ['tutorial1', 'tutorial2']}",
                }
            ],
        },
    ]


def test_get_anthropic_parts_from_chat_parts_single_text():
    """Test converting single text part."""
    parts = [TextPart(type="text", text="Single message")]

    result = get_anthropic_parts_from_chat_parts(parts)
    assert result == [{"type": "text", "text": "Single message"}]


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
    parts = [
        ToolInvocationPart(
            type="tool-calculator",
            tool_call_id="call_456",
            state="output-available",
            input={"expression": "2 + 2"},
            output={"answer": 4},
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
