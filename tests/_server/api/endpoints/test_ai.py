# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._config.manager import UserConfigManager
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.api.endpoints.ai import make_stream_response
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
                    "code": "import pandas as pd",
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = oaiclient.chat.completions.create.call_args.kwargs[
                "messages"
            ][1]["content"]
            assert prompt == (
                "Help me create a dataframe\n\n<current-code>\nimport pandas as pd\n</current-code>"
            )

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
                    "code": "import pandas as pd",
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
                    "code": "import pandas as pd",
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the base_url it was called with
            base_url = openai_mock.call_args.kwargs["base_url"]
            assert base_url == "https://my-openai-instance.com"


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
                    "code": "import pandas as pd",
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt: str = anthropic_client.messages.create.call_args.kwargs[
                "messages"
            ][0]["content"]
            assert prompt == (
                "Help me create a dataframe\n\n<current-code>\nimport pandas as pd\n</current-code>"
            )


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
                    "code": "import pandas as pd",
                    "include_other_code": "",
                },
            )
            assert response.status_code == 200, response.text
            # Assert the prompt it was called with
            prompt = google_client.generate_content.call_args.kwargs[
                "contents"
            ]
            assert prompt == (
                "Help me create a dataframe\n\n<current-code>\nimport pandas as pd\n</current-code>"
            )

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


@contextmanager
def openai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config(
            {"ai": {"open_ai": {"api_key": "fake-api", "model": ""}}}
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
                }
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
                        "model": "",
                    }
                }
            }
        )
        yield
    finally:
        config.save_config(prev_config)


@contextmanager
def no_openai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config({"ai": {"open_ai": {"api_key": "", "model": ""}}})
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
                }
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
                }
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
                }
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
                }
            }
        )
        yield
    finally:
        config.save_config(prev_config)


class TestStreamResponse(unittest.TestCase):
    def simulate_stream(self, contents: list[str]) -> Any:
        @dataclass
        class MockContent:
            content: str

        class MockDelta:
            def __init__(self, content: str) -> None:
                self.delta = MockContent(content)

        class MockChunk:
            def __init__(self, content: str) -> None:
                self.choices = [MockDelta(content)]

        for content in contents:
            yield MockChunk(content)

    def test_no_code_fence(self):
        response = self.simulate_stream(["Hello, world!"])
        result = list(make_stream_response(response))
        assert result == ["Hello, world!"]

    def test_single_complete_code_fence(self):
        response = self.simulate_stream(
            ["```python\nprint('Hello, world!')\n```"]
        )
        result = list(make_stream_response(response))
        assert result == ["print('Hello, world!')\n"]

    def test_code_fence_across_chunks(self):
        response = self.simulate_stream(
            [
                "```python\nprint('Hello,",
                " world!')\n```",
            ]
        )
        result = list(make_stream_response(response))
        assert result == [
            "print('Hello,",
            " world!')\n",
        ]

    def test_code_fence_across_more_chunks(self):
        response = self.simulate_stream(
            [
                "```",
                "python",
                "\nprint('Hello,",
                " world!')\n",
                "```",
            ]
        )
        result = list(make_stream_response(response))
        assert result == ["print('Hello,", " world!')\n", ""]

    def test_multiple_code_fences(self):
        response = self.simulate_stream(
            [
                "```python\nprint('Hello',",
                " 'world!')\n```",
                "No code here",
                "```sql\nSELECT * FROM users;\n```",
            ]
        )
        result = list(make_stream_response(response))
        assert result == [
            "print('Hello',",
            " 'world!')\n",
            "No code here",
            "SELECT * FROM users;\n",
        ]

    def test_nested_code_fences(self):
        response = self.simulate_stream(
            ["```python\nprint('```nested```')\n```"]
        )
        result = list(make_stream_response(response))
        assert result == ["print('```nested```')\n"]

        @staticmethod
        @with_session(SESSION_ID)
        @patch("openai.OpenAI")
        def test_chat_without_code(
            client: TestClient, openai_mock: Any
        ) -> None:
            user_config_manager = get_session_config_manager(client)

            oaiclient = MagicMock()
            openai_mock.return_value = oaiclient

            oaiclient.chat.completions.create.return_value = [
                FakeChoices(
                    choices=[
                        Choice(
                            delta=Delta(content="Hello, how can I help you?")
                        )
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
                        "id": "123",
                    },
                )
                assert response.status_code == 200, response.text
                # Assert the prompt it was called with
                prompt = oaiclient.chat.completions.create.call_args.kwargs[
                    "messages"
                ][1]["content"]
                assert prompt == "Hello"

        @staticmethod
        @with_session(SESSION_ID)
        @patch("openai.OpenAI")
        def test_chat_with_code(client: TestClient, openai_mock: Any) -> None:
            user_config_manager = get_session_config_manager(client)

            oaiclient = MagicMock()
            openai_mock.return_value = oaiclient

            oaiclient.chat.completions.create.return_value = [
                FakeChoices(
                    choices=[
                        Choice(delta=Delta(content="import pandas as pd"))
                    ]
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
                        "id": "123",
                    },
                )
                assert response.status_code == 200, response.text
                # Assert the prompt it was called with
                prompt = oaiclient.chat.completions.create.call_args.kwargs[
                    "messages"
                ][1]["content"]
                assert prompt == "Help me create a dataframe"
