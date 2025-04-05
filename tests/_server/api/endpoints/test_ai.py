# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from marimo._config.manager import UserConfigManager
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.prompts import FILL_ME_TAG
from marimo._server.ai.providers import (
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

        with no_openai_config(user_config_manager):
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

        with openai_config(user_config_manager):
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

        with openai_config(user_config_manager):
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

        with openai_config_custom_model(user_config_manager):
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

        with openai_config_custom_base_url(user_config_manager):
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

        with openai_config(user_config_manager):
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

        with no_openai_config(user_config_manager):
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

        with openai_config(user_config_manager):
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

        with no_anthropic_config(user_config_manager):
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

        with anthropic_config(user_config_manager):
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

        with anthropic_config(user_config_manager):
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
    @patch("google.generativeai.GenerativeModel")
    def test_google_ai_completion_with_code(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        google_client.predict.return_value = MagicMock(
            text="import pandas as pd"
        )

        with google_ai_config(user_config_manager):
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
            prompt = google_client.generate_content.call_args.kwargs[
                "contents"
            ]
            assert prompt[0]["parts"][0] == "Help me create a dataframe"

    @staticmethod
    @with_session(SESSION_ID)
    @patch("google.generativeai.GenerativeModel")
    def test_google_ai_completion_without_token(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        del google_ai_mock
        user_config_manager = get_session_config_manager(client)

        with no_google_ai_config(user_config_manager):
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
    @patch("google.generativeai.GenerativeModel")
    def test_google_ai_inline_completion(
        client: TestClient, google_ai_mock: Any
    ) -> None:
        user_config_manager = get_session_config_manager(client)

        google_client = MagicMock()
        google_ai_mock.return_value = google_client

        google_client.predict.return_value = MagicMock(
            text="df = pd.DataFrame()"
        )

        with google_ai_config(user_config_manager):
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
            prompt = google_client.generate_content.call_args.kwargs[
                "contents"
            ]
            assert (
                prompt[0]["parts"][0]
                == f"import pandas as pd\n{FILL_ME_TAG}\ndf.head()"
            )


@contextmanager
def openai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {
                        "api_key": "fake-api",
                        "model": "some-openai-model",
                    }
                },
                "completion": {
                    "model": "gpt-marimo-for-inline-completion",
                    "api_key": "fake-api",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def openai_config_custom_model(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
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
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def openai_config_custom_base_url(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {
                        "api_key": "fake-api",
                        "base_url": "https://my-openai-instance.com",
                        "model": "some-openai-model-with-base-url",
                    }
                },
                "completion": {
                    "model": "gpt-marimo-for-inline-completion",
                    "api_key": "fake-api",
                    "base_url": "https://my-openai-instance.com",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def no_openai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {"open_ai": {"api_key": "", "model": ""}},
                "completion": {
                    "model": "gpt-marimo-for-inline-completion",
                    "api_key": "",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def no_anthropic_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {"model": "claude-3.5"},
                    "anthropic": {"api_key": ""},
                },
                "completion": {
                    "model": "claude-3.5-for-inline-completion",
                    "api_key": "",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def anthropic_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {"model": "claude-3.5"},
                    "anthropic": {"api_key": "fake-key"},
                },
                "completion": {
                    "model": "claude-3.5-for-inline-completion",
                    "api_key": "fake-key",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def google_ai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {"model": "gemini-1.5-pro"},
                    "google": {"api_key": "fake-key"},
                },
                "completion": {
                    "model": "gemini-1.5-pro-for-inline-completion",
                    "api_key": "fake-key",
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def no_google_ai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {
                "ai": {
                    "open_ai": {"model": "gemini-1.5-pro"},
                    "google": {"api_key": ""},
                },
            }
        )
        yield
    finally:
        config.save_config(prev_config)


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

        with openai_config(user_config_manager):
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

        with openai_config(user_config_manager):
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
        provider = OpenAIProvider(model="gpt-4o", config={})
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
        provider = OpenAIProvider(model="gpt-4o", config={})
        result = provider.extract_content(mock_response)

        # Assert that the result is the expected content
        assert result == "Test content"


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
    ],
)
def test_without_wrapping_backticks(chunks: list[str], expected: str) -> None:
    result = list(without_wrapping_backticks(iter(chunks)))
    assert "".join(result) == expected
