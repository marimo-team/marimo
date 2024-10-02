from __future__ import annotations

from typing import List

import pytest

from marimo._plugins.ui._impl.chat.convert import (
    convert_to_anthropic_messages,
    convert_to_google_messages,
    convert_to_openai_messages,
)
from marimo._plugins.ui._impl.chat.types import (
    ChatAttachment,
    ChatMessage,
)
from marimo._plugins.ui._impl.chat.utils import from_chat_message_dict


@pytest.fixture
def sample_messages() -> List[ChatMessage]:
    return [
        ChatMessage(
            role="user",
            content="Hello, I have a question.",
            attachments=[
                ChatAttachment(
                    name="image.png",
                    content_type="image/png",
                    url="http://example.com/image.png",
                ),
                ChatAttachment(
                    name="text.txt",
                    content_type="text/plain",
                    url="http://example.com/text.txt",
                ),
            ],
        ),
        ChatMessage(
            role="assistant",
            content="Sure, I'd be happy to help. What's your question?",
            attachments=[],
        ),
    ]


def test_convert_to_openai_messages(sample_messages: List[ChatMessage]):
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
        "image_url": {"url": "http://example.com/image.png"},
    }
    assert result[0]["content"][2] == {
        "type": "text",
        "text": "http://example.com/text.txt",
    }

    # Check assistant message
    assert result[1]["role"] == "assistant"
    assert len(result[1]["content"]) == 1
    assert result[1]["content"][0] == {
        "type": "text",
        "text": "Sure, I'd be happy to help. What's your question?",
    }


def test_convert_to_anthropic_messages(sample_messages: List[ChatMessage]):
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
        "type": "image_url",
        "image_url": {"url": "http://example.com/image.png"},
    }
    assert result[0]["content"][2] == {
        "type": "text",
        "text": "http://example.com/text.txt",
    }

    # Check assistant message
    assert result[1]["role"] == "assistant"
    assert len(result[1]["content"]) == 1
    assert result[1]["content"][0] == {
        "type": "text",
        "text": "Sure, I'd be happy to help. What's your question?",
    }


def test_convert_to_google_messages(sample_messages: List[ChatMessage]):
    result = convert_to_google_messages(sample_messages)

    assert len(result) == 2

    # Check user message
    assert result[0]["role"] == "user"
    assert result[0]["parts"] == [
        "Hello, I have a question.\n"
        "[Image: http://example.com/image.png]\n"
        "[Text: http://example.com/text.txt]"
    ]

    # Check assistant message
    assert result[1]["role"] == "model"
    assert result[1]["parts"] == [
        "Sure, I'd be happy to help. What's your question?"
    ]


def test_empty_messages():
    empty_messages = []
    assert convert_to_openai_messages(empty_messages) == []
    assert convert_to_anthropic_messages(empty_messages) == []
    assert convert_to_google_messages(empty_messages) == []


def test_message_without_attachments():
    messages = [
        ChatMessage(
            role="user", content="Just a simple message", attachments=[]
        )
    ]

    openai_result = convert_to_openai_messages(messages)
    assert len(openai_result) == 1
    assert openai_result[0]["role"] == "user"
    assert len(openai_result[0]["content"]) == 1
    assert openai_result[0]["content"][0] == {
        "type": "text",
        "text": "Just a simple message",
    }

    anthropic_result = convert_to_anthropic_messages(messages)
    assert len(anthropic_result) == 1
    assert anthropic_result[0]["role"] == "user"
    assert len(anthropic_result[0]["content"]) == 1
    assert anthropic_result[0]["content"][0] == {
        "type": "text",
        "text": "Just a simple message",
    }

    google_result = convert_to_google_messages(messages)
    assert len(google_result) == 1
    assert google_result[0]["role"] == "user"
    assert google_result[0]["parts"] == ["Just a simple message"]


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

    # Test case 3: Input is already a ChatMessage
    existing_chat_message = ChatMessage(
        role="system", content="System message", attachments=None
    )

    result_existing = from_chat_message_dict(existing_chat_message)

    assert result_existing is existing_chat_message
