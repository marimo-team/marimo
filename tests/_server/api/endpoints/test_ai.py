# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.prompts import (
    FIM_MIDDLE_TAG,
    FIM_PREFIX_TAG,
    FIM_SUFFIX_TAG,
)
from marimo._server.ai.providers import (
    OpenAIProvider,
    without_wrapping_backticks,
)
from marimo._server.ai.tools.types import ToolCallResult
from tests._server.conftest import get_session_config_manager
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}

HAS_OPEN_AI_DEPS = DependencyManager.openai.has()
HAS_ANTHROPIC_DEPS = DependencyManager.anthropic.has()
HAS_GOOGLE_AI_DEPS = DependencyManager.google_ai.has()


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


@pytest.mark.skipif(
    not HAS_OPEN_AI_DEPS, reason="optional dependencies not installed"
)
class TestOpenAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_without_token(
        client: TestClient, openai_mock: Any
    ) -> None:
        del openai_mock
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
    @patch("openai.AsyncOpenAI")
    def test_completion_without_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            assert response.status_code == 200, "nope"
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"][0]["text"]
            assert prompt == ("Help me create a dataframe")
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "some-openai-model"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.AsyncOpenAI")
    def test_completion_with_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"][0]["text"]
            assert prompt == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.AsyncOpenAI")
    def test_completion_with_custom_model(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "gpt-marimo"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.AsyncOpenAI")
    def test_completion_with_custom_base_url(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the base_url it was called with
            base_url = openai_mock.call_args.kwargs["base_url"]
            assert base_url == "https://my-openai-instance.com"
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "some-openai-model-with-base-url"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.AsyncOpenAI")
    def test_inline_completion(client: TestClient, openai_mock: Any) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="df = pd.DataFrame()"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"][0]["text"]
            assert (
                prompt
                == f"{FIM_PREFIX_TAG}import pandas as pd\n{FIM_SUFFIX_TAG}\ndf.head(){FIM_MIDDLE_TAG}"
            )
            # Assert the system prompt for FIM models
            system_prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][0]["content"][0]["text"]
            assert (
                system_prompt
                == f"You are a python code completion assistant. Complete the missing code between the prefix and suffix while maintaining proper syntax, style, and functionality.Only output the code that goes after the {FIM_SUFFIX_TAG} part. Do not add any explanation or markdown."
            )
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "gpt-marimo-for-inline-completion"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_inline_completion_without_token(
        client: TestClient, openai_mock: Any
    ) -> None:
        del openai_mock
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
    @patch("openai.AsyncOpenAI")
    def test_inline_completion_different_language(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="SELECT 1;"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the system prompt for FIM models
            system_prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][0]["content"][0]["text"]
            assert (
                system_prompt
                == f"You are a sql code completion assistant. Complete the missing code between the prefix and suffix while maintaining proper syntax, style, and functionality.Only output the code that goes after the {FIM_SUFFIX_TAG} part. Do not add any explanation or markdown."
            )
            # Assert model
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "gpt-marimo-for-inline-completion"


@pytest.mark.skipif(
    not HAS_ANTHROPIC_DEPS, reason="optional dependencies not installed"
)
class TestAnthropicAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch("anthropic.Client")
    def test_anthropic_completion_without_token(
        client: TestClient, anthropic_mock: Any
    ) -> None:
        del anthropic_mock
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
    @patch("anthropic.AsyncClient")
    def test_anthropic_completion_with_code(
        client: TestClient, anthropic_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        anthropic_client = MagicMock()
        anthropic_mock.return_value = anthropic_client

        # Mock async stream
        async def mock_stream():
            yield RawContentBlockDeltaEvent(TextDelta("import pandas as pd"))

        anthropic_client.messages.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the prompt it was called with
            prompt: str = anthropic_client.messages.create.call_args.kwargs[
                "messages"
            ][0]["content"][0]["text"]
            assert prompt == "Help me create a dataframe"
            # Assert the model it was called with
            model = anthropic_client.messages.create.call_args.kwargs["model"]
            assert model == "claude-3.5"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("anthropic.AsyncClient")
    def test_anthropic_inline_completion(
        client: TestClient, anthropic_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        anthropic_client = MagicMock()
        anthropic_mock.return_value = anthropic_client

        # Mock async stream
        async def mock_stream():
            yield RawContentBlockDeltaEvent(TextDelta("df = pd.DataFrame()"))

        anthropic_client.messages.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the prompt it was called with
            prompt: str = anthropic_client.messages.create.call_args.kwargs[
                "messages"
            ][0]["content"][0]["text"]
            assert (
                prompt
                == f"{FIM_PREFIX_TAG}import pandas as pd\n{FIM_SUFFIX_TAG}\ndf.head(){FIM_MIDDLE_TAG}"
            )
            # Assert the model it was called with
            model = anthropic_client.messages.create.call_args.kwargs["model"]
            assert model == "claude-3.5-for-inline-completion"


@pytest.mark.skipif(
    not HAS_GOOGLE_AI_DEPS, reason="optional dependencies not installed"
)
class TestGoogleAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.genai.client.AsyncClient")
    def test_google_ai_completion_with_code(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        # Mock async stream
        async def mock_stream():
            yield MagicMock(
                text="import pandas as pd",
                thought=None,
            )

        google_client.models.generate_content_stream = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            # Assert the prompt it was called with
            prompt = (
                google_client.models.generate_content_stream.call_args.kwargs[
                    "contents"
                ]
            )
            assert (
                prompt[0]["parts"][0]["text"] == "Help me create a dataframe"
            )

    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.genai.Client")
    def test_google_ai_completion_without_token(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        # Mock the google client and its aio attribute
        google_client_mock = MagicMock()
        google_aio_mock = MagicMock()
        google_client_mock.aio = google_aio_mock
        google_ai_mock.return_value = google_client_mock

        # Mock async stream
        async def mock_stream():
            yield MagicMock(
                text="import pandas as pd",
                thought=None,
            )

        google_aio_mock.models.generate_content_stream = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

        config = {
            "ai": {
                "open_ai": {"model": "gemini-1.5-pro"},
                "google": {"api_key": ""},
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
                    "includeOtherCode": "",
                    "code": "",
                },
            )

        assert response.status_code == 200, response.text
        prompt = (
            google_aio_mock.models.generate_content_stream.call_args.kwargs[
                "contents"
            ]
        )
        assert prompt[0]["parts"][0]["text"] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.genai.client.AsyncClient")
    def test_google_ai_inline_completion(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        # Mock async stream
        async def mock_stream():
            yield MagicMock(
                text="df = pd.DataFrame()",
                thought=None,
            )

        google_client.models.generate_content_stream = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

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
            prompt = (
                google_client.models.generate_content_stream.call_args.kwargs[
                    "contents"
                ]
            )
            assert (
                prompt[0]["parts"][0]["text"]
                == f"{FIM_PREFIX_TAG}import pandas as pd\n{FIM_SUFFIX_TAG}\ndf.head(){FIM_MIDDLE_TAG}"
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


@with_session(SESSION_ID)
def test_chat_without_code(client: TestClient) -> None:
    user_config_manager = get_session_config_manager(client)

    with patch("openai.AsyncOpenAI") as openai_mock:
        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[
                    Choice(delta=Delta(content="Hello, how can I help you?"))
                ]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/chat",
                headers=HEADERS,
                json={
                    "messages": _create_messages("Hello"),
                    "model": "gpt-4-turbo",
                    "variables": [],
                    "includeOtherCode": "",
                    "context": {},
                    "id": "123",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"][0]["text"]
            assert prompt == "Hello"


@with_session(SESSION_ID)
def test_chat_with_code(client: TestClient) -> None:
    user_config_manager = get_session_config_manager(client)

    with patch("openai.AsyncOpenAI") as openai_mock:
        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        # Mock async stream
        async def mock_stream():
            yield FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )

        oaiclient.chat.completions.create = AsyncMock(
            side_effect=lambda **kwargs: mock_stream()  # noqa: ARG005
        )

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/chat",
                headers=HEADERS,
                json={
                    "messages": _create_messages("Help me create a dataframe"),
                    "model": "gpt-4-turbo",
                    "variables": [],
                    "includeOtherCode": "import pandas as pd",
                    "context": {},
                    "id": "123",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"][0]["text"]
            assert prompt == "Help me create a dataframe"


class TestGetContent(unittest.TestCase):
    def test_extract_content_with_none_delta(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with choices but delta is None
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].delta = None

        # Ensure text attribute doesn't exist to avoid fallback
        type(mock_response).text = property(lambda _: None)

        # Call get_content with the mock response
        result = provider.extract_content(mock_response)

        # Assert that the result is None
        assert result is None

    def test_extract_content_with_delta_content(self) -> None:
        # Create a mock response with choices and delta.content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].delta = Mock()
        mock_response.choices[0].delta.content = "Test content"

        # Call get_content with the mock response
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        result = provider.extract_content(mock_response)

        # Assert that the result is not None and has expected content
        assert result is not None
        result_text, result_type = result[0]
        assert result_text == "Test content"
        assert result_type == "text"


class TestGetFinishReason(unittest.TestCase):
    def test_get_finish_reason_with_no_choices(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with no choices
        mock_response = Mock()
        mock_response.choices = []

        # Call get_finish_reason with the mock response
        result = provider.get_finish_reason(mock_response)

        # Assert that the result is None
        assert result is None

    def test_get_finish_reason_with_none_finish_reason(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with choices but finish_reason is None
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = None

        # Call get_finish_reason with the mock response
        result = provider.get_finish_reason(mock_response)

        # Assert that the result is None
        assert result is None

    def test_get_finish_reason_with_tool_calls(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with choices and finish_reason = "tool_calls"
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "tool_calls"

        # Call get_finish_reason with the mock response
        result = provider.get_finish_reason(mock_response)

        # Assert that the result is "tool_calls"
        assert result == "tool_calls"

    def test_get_finish_reason_with_stop(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with choices and finish_reason = "stop"
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "stop"

        # Call get_finish_reason with the mock response
        result = provider.get_finish_reason(mock_response)

        # Assert that the result is "stop"
        assert result == "stop"

    def test_get_finish_reason_with_other_reason(self) -> None:
        config = AnyProviderConfig(base_url=None, api_key="test-key")
        provider = OpenAIProvider(model="gpt-4o", config=config)
        # Create a mock response with choices and finish_reason = "length"
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "length"

        # Call get_finish_reason with the mock response
        result = provider.get_finish_reason(mock_response)

        # Assert that the result is "stop" (fallback for non-tool_calls reasons)
        assert result == "stop"


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
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
            "print('hello')\n",
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
