from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.ai_formatters import GoogleAiFormatter
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
