from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

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
    from google.genai.types import (
        Candidate,
        Content,
        GenerateContentResponse,
        Part,
    )

    mock_md.side_effect = lambda x: Html(f"<md>{x}</md>")

    def create_response(text: str) -> GenerateContentResponse:
        return GenerateContentResponse(
            candidates=[Candidate(content=Content(parts=[Part(text=text)]))]
        )

    # Test direct GenerateContentResponse
    mock_response = create_response("# Hello")
    formatter = get_formatter(mock_response)
    assert formatter is not None
    result = formatter(mock_response)
    assert result == (
        "text/html",
        "<md># Hello</md>",
    )
    # Verify md.md was called with the normal response text
    mock_md.assert_called_with("# Hello")

    # Test streaming response (iterator)
    mock_chunk1 = MagicMock(spec=GenerateContentResponse)
    mock_chunk1.text = "```python\ndef foo():\n"
    mock_chunk2 = MagicMock(spec=GenerateContentResponse)
    mock_chunk2.text = "    pass\n```"

    # Create an iterator that is NOT a GenerateContentResponse
    mock_iterator = iter([mock_chunk1, mock_chunk2])

    # Reset the mock before the streaming call
    mock_md.reset_mock()
    result = formatter(mock_iterator)
    # Check that md.md was called 3 times (once for each chunk, then final)
    assert mock_md.call_count == 3
    assert mock_md.call_args_list == [
        call("```python\ndef foo():\n\n```"),  # First chunk with closing fence
        call("```python\ndef foo():\n    pass\n```"),  # Accumulated chunks
        call("```python\ndef foo():\n    pass\n```"),  # Final result
    ]


@pytest.mark.skipif(
    not DependencyManager.openai.has(), reason="OpenAI is not installed"
)
@patch("marimo._output.formatters.ai_formatters.md.md")
def test_register_with_openai(mock_md: MagicMock):
    from openai.types.chat.chat_completion import ChatCompletion, Choice
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from openai.types.completion import Completion
    from openai.types.completion_choice import CompletionChoice

    OpenAIFormatter().register()
    mock_md.side_effect = lambda x: Html(f"<md>{x}</md>")

    # Test completion
    mock_completion = Completion(
        id="1",
        created=123,
        model="test",
        object="text_completion",
        choices=[
            CompletionChoice(
                text="Hello world",
                index=0,
                logprobs=None,
                finish_reason="stop",
            )
        ],
    )
    formatter = get_formatter(mock_completion)
    assert formatter is not None
    result = formatter(mock_completion)
    assert result == ("text/html", "<md>Hello world</md>")
    mock_md.assert_called_with("Hello world")

    # Test chat completion
    mock_chat = ChatCompletion(
        id="1",
        created=123,
        model="test",
        object="chat.completion",
        choices=[
            Choice(
                index=0,
                logprobs=None,
                finish_reason="stop",
                message=ChatCompletionMessage(
                    role="assistant", content="Chat response"
                ),
            )
        ],
    )
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
