# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.prompts import FILL_ME_TAG
from marimo._server.ai.providers import (
    AnyProviderConfig,
    OpenAIProvider,
    without_wrapping_backticks,
)
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
                    "include_other_code": "",
                    "code": "",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "OpenAI API key not configured"}

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_without_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

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
                    "include_other_code": "",
                    "code": "",
                },
            )
            assert response.status_code == 200, "nope"
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
            assert prompt == ("Help me create a dataframe")
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "some-openai-model"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_with_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

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
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
            assert prompt == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_with_custom_model(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

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
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the model it was called with
            model = oaiclient.chat.completions.create.call_args.kwargs["model"]
            assert model == "gpt-marimo"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_with_custom_base_url(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

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
                    "include_other_code": "",
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
    @patch("openai.OpenAI")
    def test_inline_completion(client: TestClient, openai_mock: Any) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="df = pd.DataFrame()"))]
            )
        ]

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
            ][1]["content"]
            assert prompt == f"import pandas as pd\n{FILL_ME_TAG}\ndf.head()"
            # Assert the system prompt includes language-specific instructions
            system_prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][0]["content"]
            assert "python" in system_prompt
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
            "detail": "AI completion API key not configured"
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_inline_completion_different_language(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(choices=[Choice(delta=Delta(content="SELECT 1;"))])
        ]

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
            # Assert the system prompt includes language-specific instructions
            system_prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][0]["content"]
            assert "sql" in system_prompt
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
                    "include_other_code": "",
                    "code": "",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "Anthropic API key not configured"
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch("anthropic.Client")
    def test_anthropic_completion_with_code(
        client: TestClient, anthropic_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        anthropic_client = MagicMock()
        anthropic_mock.return_value = anthropic_client

        anthropic_client.messages.create.return_value = [
            RawContentBlockDeltaEvent(TextDelta("import pandas as pd"))
        ]

        with patch.object(
            user_config_manager, "get_config", return_value=_anthropic_config()
        ):
            response = client.post(
                "/api/ai/completion",
                headers=HEADERS,
                json={
                    "prompt": "Help me create a dataframe",
                    "code": "<rewrite_this>import pandas as pd</rewrite_this>",
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt: str = anthropic_client.messages.create.call_args.kwargs[
                "messages"
            ][0]["content"]
            assert prompt == "Help me create a dataframe"
            # Assert the model it was called with
            model = anthropic_client.messages.create.call_args.kwargs["model"]
            assert model == "claude-3.5"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("anthropic.Client")
    def test_anthropic_inline_completion(
        client: TestClient, anthropic_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        anthropic_client = MagicMock()
        anthropic_mock.return_value = anthropic_client

        anthropic_client.messages.create.return_value = [
            RawContentBlockDeltaEvent(TextDelta("df = pd.DataFrame()"))
        ]

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
            ][0]["content"]
            assert prompt == f"import pandas as pd\n{FILL_ME_TAG}\ndf.head()"
            # Assert the model it was called with
            model = anthropic_client.messages.create.call_args.kwargs["model"]
            assert model == "claude-3.5-for-inline-completion"


@pytest.mark.skipif(
    not HAS_GOOGLE_AI_DEPS, reason="optional dependencies not installed"
)
class TestGoogleAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.genai.Client")
    def test_google_ai_completion_with_code(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        google_client.models.generate_content_stream.return_value = [
            MagicMock(
                text="import pandas as pd",
                thought=None,
            )
        ]

        config = {
            "ai": {
                "open_ai": {"model": "gemini-1.5-pro"},
                "google": {"api_key": "fake-key"},
            },
            "completion": {
                "model": "gemini-1.5-pro-for-inline-completion",
                "api_key": "fake-key",
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
                    "include_other_code": "",
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
        del google_ai_mock
        user_config_manager = get_session_config_manager(client)

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
                    "include_other_code": "",
                    "code": "",
                },
            )
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": "Google AI API key not configured"
        }

    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.genai.Client")
    def test_google_ai_inline_completion(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        google_client.models.generate_content_stream.return_value = [
            MagicMock(
                text="df = pd.DataFrame()",
                thought=None,
            )
        ]

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
                == f"import pandas as pd\n{FILL_ME_TAG}\ndf.head()"
            )


def _openai_config():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "model": "openai/some-openai-model",
            }
        },
        "completion": {
            "model": "gpt-marimo-for-inline-completion",
            "api_key": "fake-api",
        },
    }


def _openai_config_custom_model():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "model": "gpt-marimo",
            }
        },
        "completion": {
            "model": "gpt-marimo-for-inline-completion",
            "api_key": "fake-api",
        },
    }


def _openai_config_custom_base_url():
    return {
        "ai": {
            "open_ai": {
                "api_key": "fake-api",
                "base_url": "https://my-openai-instance.com",
                "model": "openai/some-openai-model-with-base-url",
            }
        },
        "completion": {
            "model": "gpt-marimo-for-inline-completion",
            "api_key": "fake-api",
            "base_url": "https://my-openai-instance.com",
        },
    }


def _no_openai_config():
    return {
        "ai": {"open_ai": {"api_key": "", "model": ""}},
        "completion": {
            "model": "gpt-marimo-for-inline-completion",
            "api_key": "",
        },
    }


def _no_anthropic_config():
    return {
        "ai": {
            "open_ai": {"model": "claude-3.5"},
            "anthropic": {"api_key": ""},
        },
        "completion": {
            "model": "claude-3.5-for-inline-completion",
            "api_key": "",
        },
    }


def _anthropic_config():
    return {
        "ai": {
            "open_ai": {"model": "claude-3.5"},
            "anthropic": {"api_key": "fake-key"},
        },
        "completion": {
            "model": "claude-3.5-for-inline-completion",
            "api_key": "fake-key",
        },
    }


def _google_ai_config():
    return {
        "ai": {
            "open_ai": {"model": "gemini-1.5-pro"},
            "google": {"api_key": "fake-key"},
        },
        "completion": {
            "model": "gemini-1.5-pro-for-inline-completion",
            "api_key": "fake-key",
        },
    }


@with_session(SESSION_ID)
def test_chat_without_code(client: TestClient) -> None:
    user_config_manager = get_session_config_manager(client)

    with patch("openai.OpenAI") as openai_mock:
        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[
                    Choice(delta=Delta(content="Hello, how can I help you?"))
                ]
            )
        ]

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/chat",
                headers=HEADERS,
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "gpt-4-turbo",
                    "variables": [],
                    "include_other_code": "",
                    "context": {},
                    "id": "123",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
            assert prompt == "Hello"


@with_session(SESSION_ID)
def test_chat_with_code(client: TestClient) -> None:
    user_config_manager = get_session_config_manager(client)

    with patch("openai.OpenAI") as openai_mock:
        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

        with patch.object(
            user_config_manager, "get_config", return_value=_openai_config()
        ):
            response = client.post(
                "/api/ai/chat",
                headers=HEADERS,
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": "Help me create a dataframe",
                        }
                    ],
                    "model": "gpt-4-turbo",
                    "variables": [],
                    "include_other_code": "import pandas as pd",
                    "context": {},
                    "id": "123",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
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
        result_text, result_type = provider.extract_content(mock_response)

        # Assert that the result is the expected content
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
def test_without_wrapping_backticks(chunks: list[str], expected: str) -> None:
    result = list(without_wrapping_backticks(iter(chunks)))
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
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
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
                "tool_name": "test_tool",
                "arguments": {"param1": "value1", "param2": 42},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert response_data["tool_name"] == "test_tool"
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
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result with error as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
                tool_name="failing_tool",
                result=None,
                error="Tool execution failed: Invalid parameter",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "tool_name": "failing_tool",
                "arguments": {"invalid_param": "bad_value"},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for error case
        assert response_data["success"] is False
        assert response_data["tool_name"] == "failing_tool"
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
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result for non-existent tool as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
                tool_name="nonexistent_tool",
                result=None,
                error="Tool 'nonexistent_tool' not found. Available tools: get_server_debug_info",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={"tool_name": "nonexistent_tool", "arguments": {}},
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for not found case
        assert response_data["success"] is False
        assert response_data["tool_name"] == "nonexistent_tool"
        assert response_data["result"] is None
        assert "not found" in response_data["error"]

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_validation_error(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with validation error."""
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock tool result with validation error as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
                tool_name="test_tool",
                result=None,
                error="Invalid arguments for tool 'test_tool': Missing required parameter 'required_param'",
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "tool_name": "test_tool",
                "arguments": {"optional_param": "value"},
            },
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure for validation error
        assert response_data["success"] is False
        assert response_data["tool_name"] == "test_tool"
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
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result with complex data as a coroutine
        async def mock_invoke_tool(
            _tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
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
            json={"tool_name": "complex_tool", "arguments": complex_args},
        )

        assert response.status_code == 200, response.text
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert response_data["tool_name"] == "complex_tool"
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
            json={"tool_name": "test_tool", "arguments": {}},
        )

        # Should fail without proper session
        assert response.status_code in [400, 401, 403], response.text

    @staticmethod
    @with_session(SESSION_ID)
    @patch("marimo._server.api.endpoints.ai.get_tool_manager")
    def test_invoke_tool_empty_arguments(
        client: TestClient, mock_get_tool_manager: Any
    ) -> None:
        """Test tool invocation with empty arguments."""
        from marimo._server.ai.tools import ToolResult

        # Mock the tool manager and its response
        mock_tool_manager = MagicMock()
        mock_get_tool_manager.return_value = mock_tool_manager

        # Mock successful tool result with empty arguments
        async def mock_invoke_tool(
            tool_name: str, _arguments: dict
        ) -> ToolResult:
            return ToolResult(
                tool_name=tool_name,
                result={"message": "Tool executed with empty args"},
                error=None,
            )

        mock_tool_manager.invoke_tool = mock_invoke_tool

        response = client.post(
            "/api/ai/invoke_tool",
            headers=HEADERS,
            json={
                "tool_name": "test_tool",
                "arguments": {},  # Empty arguments
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["tool_name"] == "test_tool"
        assert data["result"]["message"] == "Tool executed with empty args"
        assert data["error"] is None
