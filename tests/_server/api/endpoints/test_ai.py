# Copyright 2024 Marimo. All rights reserved.
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from marimo._dependencies.dependencies import DependencyManager
from tests._server.conftest import get_session_manager
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
        filename = get_session_manager(client).filename
        assert filename

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
            "detail": "OpenAI API key not found in environment"
        }

    @staticmethod
    @with_session(SESSION_ID)
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @patch("openai.OpenAI")
    def test_completion_without_code(
        client: TestClient, openai_mock: Any
    ) -> None:
        filename = get_session_manager(client).filename
        assert filename

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

        with fake_openai_env():
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
        filename = get_session_manager(client).filename
        assert filename

        oaiclient = MagicMock()
        openai_mock.return_value = oaiclient

        oaiclient.chat.completions.create.return_value = [
            FakeChoices(
                choices=[Choice(delta=Delta(content="import pandas as pd"))]
            )
        ]

        with fake_openai_env():
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


@contextmanager
def fake_openai_env():
    try:
        os.environ["OPENAI_API_KEY"] = "fake-key"
        yield
    finally:
        del os.environ["OPENAI_API_KEY"]
