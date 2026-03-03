# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._server.ai.prompts import (
    FIM_MIDDLE_TAG,
    FIM_PREFIX_TAG,
    FIM_SUFFIX_TAG,
)
from marimo._server.ai.providers import (
    without_wrapping_backticks,
)
from marimo._server.ai.tools.types import ToolCallResult
from marimo._server.api.endpoints.ai import safe_stream_wrapper
from tests._server.conftest import get_session_config_manager
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


# Anthropic
@dataclass
class TextDelta:
    text: str


# Anthropic
@dataclass
class RawContentBlockDeltaEvent:
    delta: TextDelta


# OpenAI
@dataclass
class Delta:
    content: str


# OpenAI
@dataclass
class Choice:
    delta: Delta
    finish_reason: Optional[str] = None


# OpenAI
@dataclass
class FakeChoices:
    choices: list[Choice]


def _create_messages(prompt: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": prompt,
            "parts": [
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "mediaType": "text/csv",
                    "url": "data:text/csv;base64,R29vZGJ5ZQ==",
                },
            ],
        },
    ]


@pytest.mark.requires("openai", "pydantic_ai")
class TestOpenAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    def test_completion_without_token(
        client: TestClient,
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_no_openai_config(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "includeOtherCode": "",
                    "code": "",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "OpenAI API key not configured. Go to Settings > AI to configure."
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.stream_text")
    def test_completion_without_code(
        client: TestClient, mock_stream_text: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async stream
        async def mock_stream():
            yield "import pandas as pd"

        mock_stream_text.return_value = mock_stream()

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_openai_config(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "includeOtherCode": "",
                    "code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify stream_text was called
            mock_stream_text.assert_called_once()
            # Assert the prompt it was called with
            call_kwargs = mock_stream_text.call_args.kwargs
            assert call_kwargs["user_prompt"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.stream_text")
    def test_completion_with_code(
        client: TestClient, mock_stream_text: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async stream
        async def mock_stream():
            yield "import pandas as pd"

        mock_stream_text.return_value = mock_stream()

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_openai_config(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "includeOtherCode": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify stream_text was called
            mock_stream_text.assert_called_once()
            # Assert the prompt it was called with
            call_kwargs = mock_stream_text.call_args.kwargs
            assert call_kwargs["user_prompt"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.stream_text")
    def test_completion_with_custom_model(
        client: TestClient, mock_stream_text: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async stream
        async def mock_stream():
            yield "import pandas as pd"

        mock_stream_text.return_value = mock_stream()

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_openai_config_custom_model(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "includeOtherCode": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify stream_text was called
            mock_stream_text.assert_called_once()

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.stream_text")
    def test_completion_with_custom_base_url(
        client: TestClient, mock_stream_text: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async stream
        async def mock_stream():
            yield "import pandas as pd"

        mock_stream_text.return_value = mock_stream()

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_openai_config_custom_base_url(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "includeOtherCode": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify stream_text was called
            mock_stream_text.assert_called_once()

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.completion")
    def test_inline_completion(
        client: TestClient, mock_completion: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock completion to return a string
        mock_completion.return_value = "df = pd.DataFrame()"

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/inline_completion",
                headers=HEADERS,
                json={
                    "prefix": "import pandas as pd\n",
                    "suffix": "\ndf.head()",
                    "language": "python",
                },
            )
            assert response.status_code == 200, response.text
            # Verify completion was called
            mock_completion.assert_called_once()
            # Assert the messages contain FIM format
            call_kwargs = mock_completion.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 1
            # Verify FIM format is used
            assert messages[0].parts[0].text == (
                f"{FIM_PREFIX_TAG}import pandas as pd\n"
                f"{FIM_SUFFIX_TAG}\ndf.head()"
                f"{FIM_MIDDLE_TAG}"
            )

    @staticmethod
    @with_session(SESSION_ID)
    def test_inline_completion_without_token(
        client: TestClient,
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        with patch.object(
            user_config_manager, "get_config", return_value=_no_openai_config()
        ):
            response = client.post(
                "/api/ai/inline_completion",
                headers=HEADERS,
                json={
                    "prefix": "import pandas as pd\n",
                    "suffix": "\ndf.head()",
                    "language": "python",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "OpenAI API key not configured. Go to Settings > AI to configure."
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.OpenAIProvider.completion")
    def test_inline_completion_different_language(
        client: TestClient, mock_completion: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock completion to return a string
        mock_completion.return_value = "SELECT 1;"

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/inline_completion",
                headers=HEADERS,
                json={
                    "prefix": "SELECT 1;",
                    "suffix": "\nSELECT 2;",
                    "language": "sql",
                },
            )
            assert response.status_code == 200, response.text
            # Verify completion was called
            mock_completion.assert_called_once()
            # Assert the system prompt mentions SQL
            call_kwargs = mock_completion.call_args.kwargs
            assert "sql" in call_kwargs["system_prompt"].lower()


@pytest.mark.requires("anthropic", "pydantic_ai")
class TestAnthropicAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    def test_anthropic_completion_without_token(
        client: TestClient,
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        with patch.object(
            user_config_manager,
            "get_config",
            return_value=_no_anthropic_config(),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "includeOtherCode": "",
                    "code": "",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "Anthropic API key not configured. Go to Settings > AI to configure."
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch(
        "marimo._server.ai.providers.AnthropicProvider.stream_text",
        return_value=AsyncMock(),
    )
    def test_anthropic_completion_with_code(
        client: TestClient, stream_text_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async generator for stream_text
        async def mock_stream():
            yield "import pandas as pd"

        stream_text_mock.return_value = mock_stream()

        with patch.object(
            user_config_manager, "get_config", return_value=_anthropic_config()
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "includeOtherCode": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify that stream_text was called
            stream_text_mock.assert_called_once()
            # Check the user_prompt parameter
            call_kwargs = stream_text_mock.call_args.kwargs
            assert call_kwargs["user_prompt"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch(
        "marimo._server.ai.providers.AnthropicProvider.completion",
        return_value=AsyncMock(),
    )
    def test_anthropic_inline_completion(
        client: TestClient, completion_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock completion to return a string
        completion_mock.return_value = "df = pd.DataFrame()"

        with patch.object(
            user_config_manager, "get_config", return_value=_anthropic_config()
        ):
            response = client.post(
                "/api/ai/inline_completion",
                headers=HEADERS,
                json={
                    "prefix": "import pandas as pd\n",
                    "suffix": "\ndf.head()",
                    "language": "python",
                },
            )
            assert response.status_code == 200, response.text
            completion_mock.assert_called_once()
            call_kwargs = completion_mock.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 1
            assert messages[0].parts[0].text == (
                f"{FIM_PREFIX_TAG}import pandas as pd\n"
                f"{FIM_SUFFIX_TAG}\ndf.head()"
                f"{FIM_MIDDLE_TAG}"
            )


@pytest.mark.requires("google_ai", "pydantic_ai")
class TestGoogleAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch(
        "marimo._server.ai.providers.GoogleProvider.stream_text",
        return_value=AsyncMock(),
    )
    def test_google_ai_completion_with_code(
        client: TestClient, stream_text_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock async generator for stream_text
        async def mock_stream():
            yield "import pandas as pd"

        stream_text_mock.return_value = mock_stream()

        config = {
            "ai": {
                "open_ai": {"model": "gemini-1.5-pro"},
                "google": {"api_key": "fake-key"},
                "models": {
                    "autocomplete_model": "google/gemini-1.5-pro-for-inline-completion",
                },
            },
        }

        with patch.object(
            user_config_manager, "get_config", return_value=config
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "includeOtherCode": "",
                },
            )
            assert response.status_code == 200, response.text
            # Verify that stream_text was called
            stream_text_mock.assert_called_once()
            # Check the user_prompt parameter
            call_kwargs = stream_text_mock.call_args.kwargs
            assert call_kwargs["user_prompt"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    def test_google_ai_completion_without_token(
        client: TestClient,
    ) -> None:
        from marimo._server.ai.providers import PydanticProvider

        user_config_manager = get_session_config_manager(client)

        # Mock async generator for stream_text
        async def mock_stream():
            yield "import pandas as pd"

        mock_provider = MagicMock(spec=PydanticProvider)
        mock_provider.stream_text.return_value = mock_stream()

        config = {
            "ai": {
                "open_ai": {"model": "gemini-1.5-pro"},
                "google": {"api_key": ""},
            },
        }

        with (
            patch.object(
                user_config_manager, "get_config", return_value=config
            ),
            patch(
                "marimo._server.api.endpoints.ai.get_completion_provider",
                return_value=mock_provider,
            ),
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "includeOtherCode": "",
                    "code": "",
                },
            )

        assert response.status_code == 200, response.text
        # Verify that stream_text was called
        mock_provider.stream_text.assert_called_once()
        call_kwargs = mock_provider.stream_text.call_args.kwargs
        assert call_kwargs["user_prompt"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.ai.providers.GoogleProvider.completion")
    def test_google_ai_inline_completion(
        client: TestClient, completion_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock completion to return a string
        completion_mock.return_value = "df = pd.DataFrame()"

        with patch.object(
            user_config_manager, "get_config", return_value=_google_ai_config()
        ):
            response = client.post(
                "/api/ai/inline_completion",
                headers=HEADERS,
                json={
                    "prefix": "import pandas as pd\n",
                    "suffix": "\ndf.head()",
                    "language": "python",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            completion_mock.assert_called_once()
            call_kwargs = completion_mock.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 1
            assert messages[0].parts[0].text == (
                f"{FIM_PREFIX_TAG}import pandas as pd\n"
                f"{FIM_SUFFIX_TAG}\ndf.head()"
                f"{FIM_MIDDLE_TAG}"
            )


def _openai_config():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "model": "openai/some-openai-model",
            },
            "models": {
                "autocomplete_model": "gpt-marimo-for-inline-completion",
            },
        },
    }


def _openai_config_custom_model():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "model": "gpt-marimo",
            },
            "models": {
                "autocomplete_model": "gpt-marimo-for-inline-completion",
            },
        },
    }


def _openai_config_custom_base_url():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "base_url": "https://my-openai-instance.com",
                "model": "openai/some-openai-model-with-base-url",
            },
            "models": {
                "autocomplete_model": "gpt-marimo-for-inline-completion",
            },
        },
    }


def _no_openai_config():
    return {
        "ai": {
            "open_ai": {"api_key": "", "model": ""},
            "models": {
                "autocomplete_model": "gpt-marimo-for-inline-completion",
            },
        },
    }


def _no_anthropic_config():
    return {
        "ai": {
            "open_ai": {"model": "claude-3.5"},
            "anthropic": {"api_key": ""},
            "models": {
                "autocomplete_model": "claude-3.5-for-inline-completion",
            },
        },
    }


def _anthropic_config():
    return {
        "ai": {
            "open_ai": {"model": "claude-3.5"},
            "anthropic": {"api_key": "fake-key"},
            "models": {
                "autocomplete_model": "anthropic/claude-3.5-for-inline-completion",
            },
        },
    }


def _google_ai_config():
    return {
        "ai": {
            "open_ai": {"model": "gemini-1.5-pro"},
            "google": {"api_key": "fake-key"},
            "models": {
                "autocomplete_model": "google/gemini-1.5-pro-for-inline-completion",
            },
        },
    }


@pytest.mark.requires("openai", "pydantic_ai")
@with_session(SESSION_ID)
@patch("marimo._server.ai.providers.OpenAIProvider.stream_completion")
def test_chat_without_code(
    client: TestClient, mock_stream_completion: Any
) -> None:
    user_config_manager = get_session_config_manager(client)

    # Create a mock StreamingResponse
    from starlette.responses import StreamingResponse

    async def mock_stream():
        yield b"Hello, how can I help you?"

    mock_response = StreamingResponse(
        content=mock_stream(),
        media_type="text/event-stream",
    )
    mock_stream_completion.return_value = mock_response

    with patch.object(
        user_config_manager, "get_config", return_value=_openai_config()
    ):
        response = client.post(
            "/api/ai/chat",
            headers=HEADERS,
            json={
                "messages": _create_messages("Hello"),
                "uiMessages": _create_messages("Hello"),
                "model": "gpt-4-turbo",
                "variables": [],
                "includeOtherCode": "",
                "context": {},
                "id": "123",
            },
        )
        assert response.status_code == 200, response.text
        # Verify stream_completion was called
        mock_stream_completion.assert_called_once()


@pytest.mark.requires("openai", "pydantic_ai")
@with_session(SESSION_ID)
@patch("marimo._server.ai.providers.OpenAIProvider.stream_completion")
def test_chat_with_code(
    client: TestClient, mock_stream_completion: Any
) -> None:
    user_config_manager = get_session_config_manager(client)

    # Create a mock StreamingResponse
    from starlette.responses import StreamingResponse

    async def mock_stream():
        yield b"import pandas as pd"

    mock_response = StreamingResponse(
        content=mock_stream(),
        media_type="text/event-stream",
    )
    mock_stream_completion.return_value = mock_response

    with patch.object(
        user_config_manager, "get_config", return_value=_openai_config()
    ):
        response = client.post(
            "/api/ai/chat",
            headers=HEADERS,
            json={
                "messages": _create_messages("Help me create a dataframe"),
                "uiMessages": _create_messages("Help me create a dataframe"),
                "model": "gpt-4-turbo",
                "variables": [],
                "includeOtherCode": "import pandas as pd",
                "context": {},
                "id": "123",
            },
        )
        assert response.status_code == 200, response.text
        # Verify stream_completion was called
        mock_stream_completion.assert_called_once()


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        # Basic cases
        (["Hello", " world", "!"], "Hello world!"),
        (
            ["```", "print('hello')", "print('world')"],
            "print('hello')print('world')",
        ),
        (
            ["print('hello')", "print('world')", "```"],
            "print('hello')print('world')```",
        ),
        (
            ["```", "print('hello')", "```"],
            "print('hello')",
        ),
        (["Hello", " ``` ", "world"], "Hello ``` world"),
        (
            ["``", "`print('hello')", "``", "`"],
            "print('hello')",
        ),
        (
            ["``", "`", "\n", "print('hello')", "\n", "``", "`"],
            "print('hello')",
        ),
        (
            ["```\n", "print('hello')", "print('world')", "\n```"],
            "print('hello')print('world')",
        ),
        (
            ["```\nprint('hello')\n", "print('world')\n```"],
            "print('hello')\nprint('world')",
        ),
        (
            ["```\n", "def test():\n    ", "return True\n```"],
            "def test():\n    return True",
        ),
        ([], ""),
        (["```idk```"], "idk"),
        (["Hello world"], "Hello world"),
        (
            ["```python\n", "def hello():\n    ", "print('world')\n```"],
            "def hello():\n    print('world')",
        ),
        (
            ["```python", "\ndef hello():\n    ", "print('world')\n```"],
            "def hello():\n    print('world')",
        ),
        (
            ["```sql", "SELECT * FROM table", " WHERE id = 1", "```"],
            "SELECT * FROM table WHERE id = 1",
        ),
        (
            ["```sql\n", "SELECT * FROM table\n", "WHERE id = 1\n```"],
            "SELECT * FROM table\nWHERE id = 1",
        ),
        # Test trailing whitespace preservation after closing backticks
        (
            ["```", "print('hello')", "```  "],
            "print('hello')  ",
        ),
        (
            ["```python\n", "print('hello')", "\n``` "],
            "print('hello') ",
        ),
        (
            ["```", "code", "```\t\n"],
            "code\t\n",
        ),
        # Test leading whitespace before opening backticks (whitespace and backticks stripped)
        (
            ["  ```", "code", "```"],
            "code",
        ),
        (
            [" ```python\n", "code", "```"],
            "code",
        ),
        (
            ["\t```", "code", "```"],
            "code",
        ),
        (
            ["\n", "\n", "```\n", "code", "\n```\n"],
            "code\n",
        ),
        (
            ["\n", "\n", "```python\n", "code", "\n```\n"],
            "code\n",
        ),
        (
            ["\n``", "`python\n", "code", "\n```\n"],
            "code\n",
        ),
        (
            ["\n`", "`", "`python\n", "code", "\n```\n"],
            "code\n",
        ),
        # Test opening backticks with extra characters after language (language stripped, rest preserved)
        (
            ["```python ", "code", "```"],
            " code",
        ),
        (
            ["```python\t", "code", "```"],
            "\tcode",
        ),
        # Empty code block
        (["```\n", "```"], ""),
        (["```python\n", "```"], ""),
        # Only opening backticks
        (["```\n", "code"], "code"),
        (["```python\n", "code"], "code"),
        # Only closing backticks
        (["code", "\n```"], "code\n```"),
        # Multiple consecutive code blocks (keeps middle fences)
        (
            ["```\n", "x = 1\n", "```\n", "```\n", "y = 2\n", "```"],
            "x = 1\n```\n```\ny = 2\n",
        ),
        # Code block with inline backticks in content
        (
            ["```python\n", "s = 'use `backticks`'\n", "```"],
            "s = 'use `backticks`'\n",
        ),
        # Backticks split across multiple chunks
        (["``", "`\n", "code\n", "``", "`"], "code\n"),
        # Language identifier split from backticks
        (["```", "python\n", "code\n", "```"], "code\n"),
        # No newline after opening backticks
        (["```", "code", "```"], "code"),
        # Text before opening backticks (not at start, so backticks kept)
        (["prefix ", "```\n", "code\n", "```"], "prefix ```\ncode\n```"),
        # Text after closing backticks (backticks kept because followed by text)
        (["```\n", "code\n", "```", " suffix"], "code\n``` suffix"),
        # Multiple newlines
        (["```\n\n", "code\n\n", "```"], "\ncode\n\n"),
        # Whitespace handling (preserved inside code block)
        (["```\n", "  code  \n", "```"], "  code  \n"),
        # Tab characters (preserved inside code block)
        (["```\n", "\tcode\t\n", "```"], "\tcode\t\n"),
        # Mixed opening styles in same stream (middle ```python\n is kept)
        (
            ["```\n", "x\n", "```\n", "```python\n", "y\n", "```"],
            "x\n```\n```python\ny\n",
        ),
        # Unsupported language identifier (should keep it as text)
        (
            ["```javascript\n", "console.log()\n", "```"],
            "javascript\nconsole.log()\n",
        ),
        # Markdown language identifier (supported)
        (["```markdown\n", "# Title\n", "```"], "# Title\n"),
    ],
)
async def test_without_wrapping_backticks(
    chunks: list[str], expected: str
) -> None:
    async def async_iter(items):
        for item in items:
            yield item

    result = []
    async for chunk in without_wrapping_backticks(async_iter(chunks)):
        result.append(chunk)
    assert "".join(result) == expected


# Tool invocation tests (provider-agnostic)
class TestInvokeToolEndpoint:
    """Tests for the /invoke_tool endpoint."""

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_success(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test successful tool invocation."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name="test_tool",
                result={
                    "message": "Tool executed successfully",
                    "data": [1, 2, 3],
                },
                error=None,
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "toolName": "test_tool",
                "arguments": {"param1": "value1", "param2": 42},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert response_data["toolName"] == "test_tool"
        assert response_data["result"] == {
            "message": "Tool executed successfully",
            "data": [1, 2, 3],
        }
        assert response_data["error"] is None

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_with_error(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with error."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result with error as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name="failing_tool",
                result=None,
                error="Tool execution failed: Invalid parameter",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "toolName": "failing_tool",
                "arguments": {"invalid_param": "bad_value"},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for error case
        assert response_data["success"] is False
        assert response_data["toolName"] == "failing_tool"
        assert response_data["result"] is None
        assert (
            response_data["error"]
            == "Tool execution failed: Invalid parameter"
        )

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_not_found(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation when tool doesn't exist."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result for non-existent tool as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name="nonexistent_tool",
                result=None,
                error="Tool 'nonexistent_tool' not found. Available tools: get_server_debug_info",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={"toolName": "nonexistent_tool", "arguments": {}},
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for not found case
        assert response_data["success"] is False
        assert response_data["toolName"] == "nonexistent_tool"
        assert response_data["result"] is None
        assert "not found" in response_data["error"]

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_validation_error(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with validation error."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result with validation error as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name="test_tool",
                result=None,
                error="Invalid arguments for tool 'test_tool': Missing required parameter 'required_param'",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "toolName": "test_tool",
                "arguments": {"optional_param": "value"},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for validation error
        assert response_data["success"] is False
        assert response_data["toolName"] == "test_tool"
        assert response_data["result"] is None
        assert "Invalid arguments" in response_data["error"]
        assert "required_param" in response_data["error"]

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_complex_arguments(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with complex argument types."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result with complex data as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name="complex_tool",
                result={
                    "processed_data": [
                        {"id": 1, "value": "a"},
                        {"id": 2, "value": "b"},
                    ],
                    "summary": {"total": 2, "success": True},
                    "metadata": {"timestamp": "2024-01-01T00:00:00Z"},
                },
                error=None,
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        complex_args = {
            "string_param": "test string",
            "number_param": 42,
            "boolean_param": True,
            "array_param": [1, 2, 3, "four"],
            "object_param": {
                "nested_string": "nested value",
                "nested_number": 3.14,
                "nested_array": ["a", "b", "c"],
            },
        }

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={"toolName": "complex_tool", "arguments": complex_args},
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert response_data["toolName"] == "complex_tool"
        assert "processed_data" in response_data["result"]
        assert "summary" in response_data["result"]
        assert "metadata" in response_data["result"]
        assert response_data["error"] is None

    @staticmethod
    @with_session(SESSION_ID)
    def test_invoke_tool_without_session(client: TestClient) -> None:
        """Test tool invocation without valid session."""
        response = client.post(
            "/api/ai/invoke_tool",
            headers={
                "Authorization": "Bearer fake-token"
            },  # No session header
            json={"toolName": "test_tool", "arguments": {}},
        )

        # Should fail without proper session
        assert response.status_code in [400, 401, 403], response.text


class TestMCPEndpoints:
    """Tests for MCP status and refresh endpoints."""

    @staticmethod
    @with_session(SESSION_ID)
    def test_mcp_status(client: TestClient) -> None:
        """Test MCP status endpoint returns error when dependencies not installed."""
        response = client.get(
            "/api/ai/mcp/status",
            headers=HEADERS,
        )

        assert response.status_code == 200, response.text
        data = response.json()

        # Should have required fields
        assert "status" in data
        assert "servers" in data
        # Will likely error due to missing dependencies or no config
        assert data["status"] in ["ok", "partial", "error"]

    @staticmethod
    @with_session(SESSION_ID)
    def test_mcp_refresh(client: TestClient) -> None:
        """Test MCP refresh endpoint returns error when dependencies not installed."""
        response = client.post(
            "/api/ai/mcp/refresh",
            headers=HEADERS,
        )

        assert response.status_code == 200, response.text
        data = response.json()

        # Should have required fields
        assert "success" in data
        assert "servers" in data
        # Will likely fail due to missing dependencies or no config
        assert isinstance(data["success"], bool)

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_empty_arguments(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with empty arguments."""

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result with empty arguments
        async def mock_invoke_tool(
            tool_name: str, _arguments: dict
        ) -> ToolCallResult:
            return ToolCallResult(
                tool_name=tool_name,
                result={"message": "Tool executed with empty args"},
                error=None,
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "toolName": "test_tool",
                "arguments": {},  # Empty arguments
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["toolName"] == "test_tool"
        assert data["result"]["message"] == "Tool executed with empty args"
        assert data["error"] is None

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_mcp_client")
    def test_mcp_status_states(
        client: TestClient, mock_get_client: Any
    ) -> None:
        """Test MCP status returns correct state based on server statuses."""
        from marimo._server.ai.mcp import MCPServerStatus

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Test partial: some connected, some failed
        mock_client.get_all_server_statuses.return_value = {
            "server1": MCPServerStatus.CONNECTED,
            "server2": MCPServerStatus.ERROR,
        }
        response = client.get("/api/ai/mcp/status", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partial"
        assert "server2" in data["error"]

        # Test error: all failed
        mock_client.get_all_server_statuses.return_value = {
            "server1": MCPServerStatus.ERROR,
            "server2": MCPServerStatus.DISCONNECTED,
        }
        response = client.get("/api/ai/mcp/status", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"


async def test_safe_stream_wrapper_handles_errors() -> None:
    """Test safe_stream_wrapper catches and formats streaming errors."""

    async def failing_generator():
        yield "chunk1"
        raise ValueError("Stream failed")

    chunks = []
    async for chunk in safe_stream_wrapper(
        failing_generator(), text_only=True
    ):
        chunks.append(chunk)

    assert chunks[0] == "chunk1"
    assert "Stream failed" in chunks[1]
