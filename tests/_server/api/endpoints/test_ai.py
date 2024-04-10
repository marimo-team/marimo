# Copyright 2024 Marimo. All rights reserved.
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from marimo._config.manager import UserConfigManager
from marimo._dependencies.dependencies import DependencyManager
from tests._server.conftest import get_user_config_manager
from tests._server.mocks import with_session

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
}

HAS_DEPS = DependencyManager.has_openai()


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
