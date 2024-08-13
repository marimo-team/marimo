# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List
from unittest.mock import MagicMock, patch

import pytest

from marimo._config.manager import UserConfigManager
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.api.endpoints.ai import make_stream_response
from tests._server.conftest import get_user_config_manager
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}

HAS_DEPS = DependencyManager.openai.has()


@dataclass
class Delta:
    content: str


@dataclass
class Choice:
    delta: Delta


@dataclass
class FakeChoices:
    choices: List[Choice]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestAiEndpoints:
    @staticmethod
    @with_session(SESSION_ID)
    @patch("openai.OpenAI")
    def test_completion_without_token(
        client: TestClient, openai_mock: Any
    ) -> None:
        del openai_mock
        user_config_manager = get_user_config_manager(client)

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
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @patch("openai.OpenAI")
    def test_completion_without_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_user_config_manager(client)

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
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @patch("openai.OpenAI")
    def test_completion_with_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_user_config_manager(client)

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
                "Help me create a dataframe\n\nCurrent code:\nimport pandas as pd"  # noqa: E501
            )

    @staticmethod
    @with_session(SESSION_ID)
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @patch("openai.OpenAI")
    def test_completion_with_custom_model(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_user_config_manager(client)

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
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @patch("openai.OpenAI")
    def test_completion_with_custom_base_url(
        client: TestClient, openai_mock: Any
    ) -> None:
        user_config_manager = get_user_config_manager(client)

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


@contextmanager
def openai_config(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config({"ai": {"open_ai": {"api_key": "fake-api"}}})
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
        config.save_config({"ai": {"open_ai": {"api_key": ""}}})
        yield
    finally:
        config.save_config(prev_config)


class TestStreamResponse(unittest.TestCase):
    def simulate_stream(self, contents: List[str]) -> Any:
        class MockContent:
            def __init__(self, content: str) -> None:
                self.content = content

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
