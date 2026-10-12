# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import msgspec
import pytest
from starlette.testclient import TestClient

from marimo._config.config import AiConfig
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._plugins.ui._impl.tables.filter_context import (
    TABLE_FILTER_CONTEXT_MAX_BYTES,
    FilterContext,
)
from marimo._server.ai.constants import DEFAULT_MODEL
from marimo._server.ai.table_filter import build_table_filter_prompt
from marimo._server.ai.tracing import SpanInfo
from marimo._session.model import SessionMode
from tests._server.conftest import get_session_config_manager
from tests._server.mocks import get_session_manager, token_header

if TYPE_CHECKING:
    from collections.abc import Iterator

SESSION_ID = "table-filter-session"
HEADERS = {"Marimo-Session-Id": SESSION_ID, **token_header()}
ENDPOINT = "/api/ai/table-filter"


def _body() -> dict[str, Any]:
    return {
        "request": "  Show rows above the median for café\n",
        "context": {
            "row_count": None,
            "columns": [
                {
                    "name": "café : (price)",
                    "type": "number",
                    "source_type": "float64",
                    "examples": ["0", "1.5"],
                    "statistics": {"nulls": 0, "median": 1.5},
                },
                {
                    "name": "0",
                    "type": "string",
                    "source_type": "object",
                    "examples": [],
                },
            ],
            "omissions": [
                {
                    "kind": "statistics",
                    "reason": "unavailable",
                    "column": "0",
                }
            ],
        },
    }


@pytest.fixture
def session_client(client: TestClient) -> Iterator[TestClient]:
    with client.websocket_connect(
        f"/ws?session_id={SESSION_ID}", headers=token_header()
    ) as websocket:
        assert websocket.receive_text()
        try:
            yield client
        finally:
            client.post("/api/kernel/shutdown", headers=token_header())


@pytest.fixture(autouse=True)
def config(session_client: TestClient) -> Iterator[MagicMock]:
    with patch.object(
        get_session_config_manager(session_client),
        "get_config",
        return_value={
            "ai": {
                "open_ai": {"api_key": "test-key"},
                "models": {"chat_model": "openai/chat-model"},
                "max_tokens": 1234,
            }
        },
    ) as config_mock:
        yield config_mock


@pytest.fixture
def provider_factory() -> Iterator[MagicMock]:
    with patch(
        "marimo._server.api.endpoints.ai.get_completion_provider"
    ) as factory:
        factory.return_value.table_filter_completion = AsyncMock(
            return_value=SimpleNamespace(fql="column_0:>1.5", explanation=None)
        )
        yield factory


@pytest.mark.parametrize(
    ("fql", "explanation"),
    [
        ('  column_1:"café\\\\*"\n', None),
        (None, "  The unavailable statistics cannot define a threshold.\n"),
        ("invalid FQL with no server adaptation", None),
    ],
)
def test_complete_result(
    session_client: TestClient,
    provider_factory: MagicMock,
    fql: str | None,
    explanation: str | None,
) -> None:
    completion = provider_factory.return_value.table_filter_completion
    completion.return_value = SimpleNamespace(fql=fql, explanation=explanation)
    body = _body()

    response = session_client.post(ENDPOINT, headers=HEADERS, json=body)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "fql": fql,
        "explanation": explanation,
        "aliases": [
            {"name": "café : (price)", "alias": "column_0"},
            {"name": "0", "alias": "column_1"},
        ],
    }
    provider_factory.assert_called_once()
    assert provider_factory.call_args.kwargs == {
        "model": "openai/chat-model",
        "session_id": f"{SESSION_ID}:table_filter",
    }
    assert provider_factory.call_args.args[0].api_key == "test-key"
    context = msgspec.convert(body["context"], type=FilterContext)
    prompt = build_table_filter_prompt(context, body["request"])
    completion.assert_awaited_once_with(
        prompt=prompt,
        max_tokens=1234,
        span_info=SpanInfo(
            endpoint="table_filter",
            model="openai/chat-model",
            session_id=SESSION_ID,
        ),
    )
    last_message = json.loads(prompt.messages[-1]["parts"][0]["text"])
    assert last_message["request"] == body["request"]
    assert last_message["context"] == body["context"]


@pytest.mark.parametrize(
    ("ai_config", "model"),
    [
        (
            {
                "open_ai": {"api_key": "test-key", "model": "legacy"},
                "models": {
                    "chat_model": "openai/current",
                    "edit_model": "edit",
                },
            },
            "openai/current",
        ),
        ({"open_ai": {"api_key": "test-key", "model": "legacy"}}, "legacy"),
        ({"open_ai": {"api_key": "test-key"}}, DEFAULT_MODEL),
    ],
)
def test_chat_model_fallback(
    session_client: TestClient,
    config: MagicMock,
    provider_factory: MagicMock,
    ai_config: AiConfig,
    model: str,
) -> None:
    config.return_value = {"ai": ai_config}
    response = session_client.post(ENDPOINT, headers=HEADERS, json=_body())

    assert response.status_code == 200, response.text
    assert provider_factory.call_args.kwargs["model"] == model
    completion = provider_factory.return_value.table_filter_completion
    assert completion.call_args.kwargs["max_tokens"] is None
    assert completion.call_args.kwargs["span_info"].model == model


@pytest.mark.parametrize("request_text", ["", " \t\r\n"])
def test_empty_request(
    session_client: TestClient,
    provider_factory: MagicMock,
    request_text: str,
) -> None:
    body = _body()
    body["request"] = request_text
    response = session_client.post(ENDPOINT, headers=HEADERS, json=body)

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The table-filter request must contain nonempty text."
    }
    provider_factory.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"request": "filter", "context": None},
        {"request": 3, "context": {}},
        {
            "request": "filter",
            "context": {"row_count": 0, "columns": [], "omissions": 1},
        },
        {
            "request": "filter",
            "context": {"row_count": "3", "columns": [], "omissions": []},
        },
        {
            "request": "filter",
            "context": {
                "row_count": 0,
                "columns": [
                    {"name": "x", "type": "invalid", "source_type": "object"}
                ],
                "omissions": [],
            },
        },
    ],
)
def test_invalid_request(
    session_client: TestClient,
    provider_factory: MagicMock,
    body: dict[str, Any],
) -> None:
    with TestClient(
        session_client.app, raise_server_exceptions=False
    ) as client:
        response = client.post(ENDPOINT, headers=HEADERS, json=body)

    assert response.status_code == 400, response.text
    assert response.json()["detail"]
    provider_factory.assert_not_called()


@pytest.mark.parametrize("refusal", ["schema", "bytes", "duplicate"])
def test_context_refusal(
    session_client: TestClient,
    config: MagicMock,
    provider_factory: MagicMock,
    refusal: str,
) -> None:
    body = _body()
    context = body["context"]
    if refusal == "schema":
        context["omissions"].append(
            {"kind": "schema", "reason": "size_limit", "count": 1}
        )
    elif refusal == "bytes":
        context["columns"][0]["name"] = "é" * TABLE_FILTER_CONTEXT_MAX_BYTES
        assert (
            len(
                encode_json_bytes(msgspec.convert(context, type=FilterContext))
            )
            > TABLE_FILTER_CONTEXT_MAX_BYTES
        )
    else:
        context["columns"][1]["name"] = context["columns"][0]["name"]
    # A refusal requires no AI configuration or optional provider dependencies.
    config.return_value = {}

    response = session_client.post(ENDPOINT, headers=HEADERS, json=body)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["fql"] is None
    assert result["explanation"]
    assert result["aliases"] == []
    assert (
        "duplicate" in result["explanation"]
        if refusal == "duplicate"
        else "context" in result["explanation"]
    )
    provider_factory.assert_not_called()


def test_context_at_byte_limit(
    session_client: TestClient, provider_factory: MagicMock
) -> None:
    body = _body()
    context = body["context"]
    context["columns"][0]["name"] = ""
    encoded_size = len(
        encode_json_bytes(msgspec.convert(context, type=FilterContext))
    )
    context["columns"][0]["name"] = "x" * (
        TABLE_FILTER_CONTEXT_MAX_BYTES - encoded_size
    )
    assert (
        len(encode_json_bytes(msgspec.convert(context, type=FilterContext)))
        == TABLE_FILTER_CONTEXT_MAX_BYTES
    )

    response = session_client.post(ENDPOINT, headers=HEADERS, json=body)

    assert response.status_code == 200, response.text
    provider_factory.return_value.table_filter_completion.assert_awaited_once()


def test_run_scope(
    session_client: TestClient, provider_factory: MagicMock
) -> None:
    with patch.object(
        get_session_manager(session_client), "mode", SessionMode.RUN
    ):
        response = session_client.post(ENDPOINT, headers=HEADERS, json=_body())

    assert response.status_code == 401, response.text
    provider_factory.assert_not_called()


def test_unauthenticated(
    session_client: TestClient, provider_factory: MagicMock
) -> None:
    response = session_client.post(
        ENDPOINT, headers={"Marimo-Session-Id": SESSION_ID}, json=_body()
    )
    assert response.status_code == 401, response.text
    provider_factory.assert_not_called()


@pytest.mark.parametrize(
    ("session_id", "detail"),
    [
        (None, "Missing Marimo-Session-Id header"),
        ("unknown-session", "Invalid session id: unknown-session"),
    ],
)
def test_invalid_session(
    session_client: TestClient,
    provider_factory: MagicMock,
    session_id: str | None,
    detail: str,
) -> None:
    headers = token_header()
    if session_id is not None:
        headers["Marimo-Session-Id"] = session_id
    with TestClient(
        session_client.app, raise_server_exceptions=False
    ) as client:
        response = client.post(ENDPOINT, headers=headers, json=_body())

    assert response.status_code == 500, response.text
    assert response.json() == {"detail": detail}
    provider_factory.assert_not_called()


@pytest.mark.parametrize(
    ("settings", "detail"),
    [
        ({}, "AI is not configured. Configure them in the settings dialog."),
        (
            {"ai": {"open_ai": {"api_key": ""}}},
            "OpenAI API key not configured. Go to Settings > AI to configure.",
        ),
        (
            {
                "ai": {
                    "models": {"chat_model": "anthropic/model"},
                    "anthropic": {"api_key": ""},
                }
            },
            "Anthropic API key not configured. Go to Settings > AI to configure.",
        ),
        (
            {
                "ai": {
                    "models": {"chat_model": "openai/model"},
                    "open_ai": {"api_key": "env:MISSING_TABLE_FILTER_KEY"},
                }
            },
            "OpenAI API key environment variable 'MISSING_TABLE_FILTER_KEY' is not set.",
        ),
    ],
)
def test_config_errors(
    session_client: TestClient,
    config: MagicMock,
    provider_factory: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, Any],
    detail: str,
) -> None:
    for name in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISSING_TABLE_FILTER_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)
    config.return_value = settings

    response = session_client.post(ENDPOINT, headers=HEADERS, json=_body())

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": detail}
    provider_factory.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("The model returned an invalid table-filter result."),
        OSError("Provider connection failed."),
    ],
)
def test_provider_errors(
    session_client: TestClient, provider_factory: MagicMock, error: Exception
) -> None:
    completion = provider_factory.return_value.table_filter_completion
    completion.side_effect = error
    with TestClient(
        session_client.app, raise_server_exceptions=False
    ) as client:
        response = client.post(ENDPOINT, headers=HEADERS, json=_body())

    assert response.status_code == 500, response.text
    assert response.json() == {"detail": str(error)}
    provider_factory.assert_called_once()
    completion.assert_awaited_once()


def test_missing_dependencies(
    session_client: TestClient, provider_factory: MagicMock
) -> None:
    provider_factory.side_effect = ManyModulesNotFoundError(
        ["pydantic_ai"],
        "Install pydantic_ai to use AI generation.",
        source="server",
    )
    with patch("marimo._server.errors.send_message_to_consumer") as notify:
        with TestClient(
            session_client.app, raise_server_exceptions=False
        ) as client:
            response = client.post(ENDPOINT, headers=HEADERS, json=_body())

    assert response.status_code == 500, response.text
    assert response.json() == {
        "detail": "Install pydantic_ai to use AI generation."
    }
    notify.assert_called_once()
    assert notify.call_args.kwargs["operation"].packages == ["pydantic_ai"]
    assert notify.call_args.kwargs["operation"].source == "server"
    provider_factory.return_value.table_filter_completion.assert_not_awaited()
