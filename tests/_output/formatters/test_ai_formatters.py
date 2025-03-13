from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from openai.types.chat import ChatCompletion
from openai.types.completion import Completion

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.ai_formatters import (
    GoogleAiFormatter,
    OpenAIFormatter,
)
from marimo._output.formatting import get_formatter
from marimo._output.hypertext import Html


@pytest.mark.skipif(
    not DependencyManager.google_ai.has(), reason="Google AI is not installed"
)
@patch(
    "marimo._output.formatters.ai_formatters.md.md",
)
def test_register_with_dummy_google(mock_md: MagicMock):
    GoogleAiFormatter().register()
    import google.generativeai as genai

    mock_md.side_effect = lambda x: Html(f"<md>{x}</md>")

    mock_response = MagicMock(genai.types.GenerateContentResponse)
    mock_response.text = "# Hello"
    mock_response._iterator = None
    mock_response.candidates = [
        MagicMock(content="# Hello", index=0, finish_reason="STOP")
    ]
    formatter = get_formatter(mock_response)
    assert formatter is not None
    result = formatter(mock_response)
    assert result == (
        "text/html",
        "<md># Hello</md>",
    )
    # Verify md.md was called with the normal response text
    mock_md.assert_called_with("# Hello")

    # Streaming response
    mock_response._iterator = iter(
        [
            MagicMock(
                text="```python\ndef foo():\n",
                index=0,
                finish_reason="INCOMPLETE",
            ),
            MagicMock(text="    pass\n```", index=1, finish_reason="STOP"),
        ]
    )
    mock_response.__iter__ = lambda self: iter(self._iterator)

    # Reset the mock before the streaming call
    mock_md.reset_mock()
    result = formatter(mock_response)
    # Check that md.md was called 3 times
    assert mock_md.call_count == 3
    assert mock_md.call_args_list == [
        call("```python\ndef foo():\n\n```"),  # First chunk
        call("```python\ndef foo():\n    pass\n```"),  # First + second chunk
        call("```python\ndef foo():\n    pass\n```"),  # End result
    ]


@pytest.mark.skipif(
    not DependencyManager.openai.has(), reason="OpenAI is not installed"
)
@patch("marimo._output.formatters.ai_formatters.md.md")
def test_register_with_openai(mock_md: MagicMock):
    OpenAIFormatter().register()
    mock_md.side_effect = lambda x: Html(f"<md>{x}</md>")

    # Test completion
    mock_completion = MagicMock(Completion)
    mock_completion.choices = [MagicMock(text="Hello world")]
    formatter = get_formatter(mock_completion)
    assert formatter is not None
    result = formatter(mock_completion)
    assert result == ("text/html", "<md>Hello world</md>")
    mock_md.assert_called_with("Hello world")

    # Test chat completion
    mock_chat = MagicMock(ChatCompletion)
    mock_chat.choices = [MagicMock(message=MagicMock(content="Chat response"))]
    formatter = get_formatter(mock_chat)
    assert formatter is not None
    result = formatter(mock_chat)
    assert result == ("text/html", "<md>Chat response</md>")
    mock_md.assert_called_with("Chat response")


@pytest.mark.skipif(
    not DependencyManager.openai.has(), reason="OpenAI is not installed"
)
@patch("marimo._output.formatters.ai_formatters.md.md")
def test_register_with_openai_streaming(mock_md: MagicMock):
    OpenAIFormatter().register()
    mock_md.side_effect = lambda x: Html(f"<md>{x}</md>")

    # TODO: Test streaming completion
    # currently hangs

    # Test streaming completion
    # mock_stream = MagicMock()
    # mock_stream.__iter__ = lambda self: iter(
    #     [
    #         Completion(
    #             id="1",
    #             choices=[MagicMock(text="Hello ")],
    #             model="test",
    #             object="completion",
    #             created=123,
    #         ),
    #         Completion(
    #             id="2",
    #             choices=[MagicMock(text="world!")],
    #             model="test",
    #             object="completion",
    #             created=123,
    #         ),
    #     ]
    # )

    # formatter = get_formatter(mock_stream)
    # assert formatter is not None
    # mock_md.reset_mock()
    # result = formatter(mock_stream)
    # assert mock_md.call_args_list == [call("Hello "), call("Hello world!")]
    # assert result == ("text/html", "<md>Hello world!</md>")

    # # Test streaming chat completion
    # mock_chat_stream = MagicMock()
    # mock_chat_stream.__iter__ = lambda self: iter(
    #     [
    #         ChatCompletionChunk(
    #             id="1",
    #             choices=[MagicMock(delta=MagicMock(content="Hi "))],
    #             model="test",
    #             object="chat.completion.chunk",
    #             created=123,
    #         ),
    #         ChatCompletionChunk(
    #             id="2",
    #             choices=[MagicMock(delta=MagicMock(content="there!"))],
    #             model="test",
    #             object="chat.completion.chunk",
    #             created=123,
    #         ),
    #     ]
    # )

    # formatter = get_formatter(mock_chat_stream)
    # assert formatter is not None
    # mock_md.reset_mock()
    # result = formatter(mock_chat_stream)
    # assert mock_md.call_args_list == [call("Hi "), call("Hi there!")]
    # assert result == ("text/html", "<md>Hi there!</md>")
