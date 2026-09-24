# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from importlib import import_module
from typing import Any
from unittest.mock import patch

import pytest

from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.providers import (
    AzureOpenAIProvider,
    CustomProvider,
    OpenAIProvider,
)

pytestmark = pytest.mark.requires("openai", "pydantic_ai")


def _events() -> list[dict[str, Any]]:
    response = {
        "id": "resp_test",
        "model": "gpt-4o",
        "created_at": 1,
        "object": "response",
        "status": "in_progress",
        "output": [],
    }
    return [
        {"type": "response.created", "response": response},
        {
            "type": "response.output_text.delta",
            "item_id": "msg_test",
            "output_index": 0,
            "content_index": 0,
            "delta": "Hello",
            "logprobs": [],
        },
        {
            "type": "response.completed",
            "response": {**response, "status": "completed"},
        },
    ]


async def _run_stream(
    events: list[dict[str, Any]],
    provider_kind: str = "openai",
    tool_calls: list[str] | None = None,
) -> str:
    import httpx
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.providers.openai import OpenAIProvider as PydanticOpenAI

    # OpenAI 3 uses httpx2; earlier SDK versions use httpx.
    if not issubclass(DefaultAsyncHttpxClient, httpx.AsyncClient):
        httpx = import_module("httpx2")

    responses: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        request_events = _events() if responses else events
        body = "".join(
            f"data: {json.dumps({**event, 'sequence_number': index})}\n\n"
            for index, event in enumerate(request_events)
        )
        response = httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )
        responses.append(response)
        return response

    def get_cell_runtime_data() -> str:
        assert tool_calls is not None
        tool_calls.append("get_cell_runtime_data")
        return "print('Hello')"

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = AsyncOpenAI(api_key="test", http_client=http_client)
        provider_class = {
            "openai": OpenAIProvider,
            "azure": AzureOpenAIProvider,
            "custom": CustomProvider,
        }[provider_kind]
        config = AnyProviderConfig(api_key="test", base_url=None)
        with patch.object(
            provider_class,
            "create_provider",
            return_value=PydanticOpenAI(openai_client=client),
        ):
            if provider_kind == "custom":
                provider = CustomProvider(
                    AiModelId.from_model("openai-responses/gpt-4o"), config
                )
            else:
                provider = provider_class("gpt-4o", config)
        try:
            agent = Agent(
                provider.create_model(),
                tools=[get_cell_runtime_data]
                if tool_calls is not None
                else [],
            )
            async with agent.run_stream("Hello") as result:
                return await result.get_output()
        finally:
            assert responses
            assert all(r.is_closed for r in responses)


@pytest.mark.parametrize("provider_kind", ["openai", "azure", "custom"])
async def test_valid_response_stream(provider_kind: str) -> None:
    assert await _run_stream(_events(), provider_kind) == "Hello"


@pytest.mark.parametrize("provider_kind", ["openai", "azure", "custom"])
@pytest.mark.parametrize("status", ["response.in_progress", "response.queued"])
@pytest.mark.parametrize("payload", [{"response": None}, {}])
async def test_empty_interim_status(
    provider_kind: str, status: str, payload: dict[str, Any]
) -> None:
    events = _events()
    # Include an empty first event as well as one after content has arrived.
    events.insert(0, {"type": status, **payload})
    events.insert(-1, {"type": status, **payload})
    assert await _run_stream(events, provider_kind) == "Hello"


@pytest.mark.parametrize("provider_kind", ["openai", "azure", "custom"])
@pytest.mark.parametrize("payload", [{"response": None}, {}])
@pytest.mark.parametrize("next_event", ["text", "tool"])
async def test_empty_created_status_is_an_error(
    provider_kind: str, payload: dict[str, Any], next_event: str
) -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    events = _events()
    # Replace the only created event, rather than inserting another before it.
    events[0] = {"type": "response.created", **payload}
    if next_event == "tool":
        events[1] = {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_test",
                "call_id": "call_test",
                "name": "get_cell_runtime_data",
                "arguments": "{}",
            },
        }
    with pytest.raises(
        UnexpectedModelBehavior,
        match="AI provider sent response.created without a response",
    ):
        await _run_stream(events, provider_kind)


@pytest.mark.parametrize(
    "status", ["response.completed", "response.failed", "response.incomplete"]
)
@pytest.mark.parametrize("payload", [{"response": None}, {}])
async def test_empty_terminal_status_is_an_error(
    status: str, payload: dict[str, Any]
) -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    events = _events()
    events[-1] = {"type": status, **payload}
    with pytest.raises(
        UnexpectedModelBehavior,
        match=f"AI provider sent {status} without a response",
    ):
        await _run_stream(events)


async def test_provider_error_is_preserved() -> None:
    from openai import APIError

    events = _events()
    events[-1] = {"error": {"message": "Rate limit exceeded"}}
    with pytest.raises(APIError, match="Rate limit exceeded"):
        await _run_stream(events)


async def test_empty_status_during_tool_call() -> None:
    events = _events()
    events[1:2] = [
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_test",
                "call_id": "call_test",
                "name": "get_cell_runtime_data",
                "arguments": "",
            },
        },
        {"type": "response.in_progress", "response": None},
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_test",
            "output_index": 0,
            "delta": "{}",
        },
    ]
    tool_calls: list[str] = []
    assert await _run_stream(events, tool_calls=tool_calls) == "Hello"
    assert tool_calls == ["get_cell_runtime_data"]
