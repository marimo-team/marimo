# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal
from unittest.mock import patch

import pytest

from marimo._plugins.ui._impl.tables.filter_context import (
    FilterContext,
    FilterContextColumn,
)
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.providers import OpenAIProvider
from marimo._server.ai.table_filter import build_table_filter_prompt
from marimo._server.ai.table_filter_output import (
    TEXT_OUTPUT_INSTRUCTIONS,
    TableFilterOutputError,
)
from marimo._server.ai.tools.types import ToolDefinition
from marimo._server.ai.tracing import SpanInfo

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage, ModelResponse
    from pydantic_ai.models.function import AgentInfo
    from pydantic_ai.profiles import ModelProfile


OutputMode = Literal["native", "tool", "text", "json-mode-only"]
MODES: list[OutputMode] = ["native", "tool", "text", "json-mode-only"]
pytestmark = pytest.mark.requires("pydantic_ai")


def _profile(mode: OutputMode) -> ModelProfile:
    from pydantic_ai.profiles import ModelProfile

    return ModelProfile(
        supports_json_schema_output=mode == "native",
        supports_tools=mode in {"native", "tool"},
        supports_json_object_output=mode == "json-mode-only",
        supports_thinking=True,
        default_structured_output_mode="prompted",
    )


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        "test",
        AnyProviderConfig(
            api_key="test-key",
            base_url=None,
            tools=[
                ToolDefinition(
                    name="configured_tool",
                    description="A configured notebook tool.",
                    parameters={"type": "object"},
                    source="backend",
                    mode=["ask"],
                )
            ],
        ),
    )


def _response(
    mode: OutputMode, info: AgentInfo, payload: str
) -> ModelResponse:
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

    if mode == "tool":
        assert len(info.output_tools) == 1
        return ModelResponse(
            [ToolCallPart(info.output_tools[0].name, payload)]
        )
    return ModelResponse([TextPart(payload)])


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("field", ["fql", "explanation"])
async def test_table_filter_completion_selects_transport_and_preserves_payload(
    mode: OutputMode,
    field: str,
) -> None:
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )
    from pydantic_ai.models.function import FunctionModel

    context = FilterContext(
        row_count=1,
        columns=[
            FilterContextColumn(
                name="東京 price", type="number", source_type="Float64"
            )
        ],
        omissions=[],
    )
    request = '  Preserve "this" request.\n  '
    prompt = build_table_filter_prompt(context, request)
    payload = '  column_0:"/^chev\\d+$/"\nFQL\nEXPLANATION\n"東京"  '
    expected_output = {"fql": None, "explanation": None, field: payload}
    response_text = (
        f"{'FQL' if field == 'fql' else 'EXPLANATION'}\n{payload}"
        if mode in {"text", "json-mode-only"}
        else json.dumps(expected_output)
    )
    calls: list[dict[str, object]] = []

    async def respond(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        user_messages = [
            part.content
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, UserPromptPart)
        ]
        assistant_messages = [
            part.content
            for message in messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, TextPart)
        ]
        output_schema = (
            info.output_tools[0].parameters_json_schema
            if info.output_tools
            else info.model_request_parameters.output_object.json_schema
            if info.model_request_parameters.output_object
            else None
        )
        calls.append(
            {
                "mode": info.model_request_parameters.output_mode,
                "settings": info.model_settings,
                "function_tools": info.function_tools,
                "native_tools": info.model_request_parameters.native_tools,
                "output_fields": sorted(output_schema["properties"])
                if output_schema
                else None,
                "required_fields": sorted(output_schema["required"])
                if output_schema
                else None,
                "extra_fields": output_schema["additionalProperties"]
                if output_schema
                else None,
                "last_user_message": user_messages[-1],
                "assistant_messages": assistant_messages,
                "text_instructions": (info.instructions or "").startswith(
                    TEXT_OUTPUT_INSTRUCTIONS
                ),
            }
        )
        return _response(mode, info, response_text)

    model = FunctionModel(respond, profile=_profile(mode))
    provider = _provider()
    span_info = SpanInfo(endpoint="table_filter", model="openai/test")
    with (
        patch.object(
            provider, "create_model", return_value=model
        ) as create_model,
        patch.object(
            provider,
            "_build_agent_capabilities",
            side_effect=AssertionError("Unexpected capabilities"),
        ),
        patch.object(
            provider,
            "_build_model_settings",
            wraps=provider._build_model_settings,
        ) as build_settings,
    ):
        output = await provider.table_filter_completion(prompt, 123, span_info)

    is_text = mode in {"text", "json-mode-only"}
    assert output.model_dump() == expected_output
    assert calls == [
        {
            "mode": "text" if is_text else mode,
            "settings": {
                "max_tokens": 123,
                "openai_reasoning_summary": "auto",
            },
            "function_tools": [],
            "native_tools": [],
            "output_fields": None if is_text else ["explanation", "fql"],
            "required_fields": None if is_text else ["explanation", "fql"],
            "extra_fields": None if is_text else False,
            "last_user_message": prompt.messages[-1]["parts"][0]["text"],
            "assistant_messages": [
                'FQL\nvehicle_make:"chev*"',
                'FQL\nactive:true AND (vehicle_make="chevrolet" OR price>1500)',
                "FQL\nvehicle_make:null OR dispatch_time:null",
                "EXPLANATION\nThe table has no horsepower column.",
                "EXPLANATION\nThe median price is unavailable. Provide a concrete price threshold instead.",
            ]
            if is_text
            else [
                message["parts"][0]["text"]
                for message in prompt.messages
                if message["role"] == "assistant"
            ],
            "text_instructions": is_text,
        }
    ]
    assert span_info.tool_count == 0
    create_model.assert_called_once_with()
    build_settings.assert_called_once_with(model, 123)


@pytest.mark.parametrize("mode", ["native", "tool"])
@pytest.mark.parametrize(
    "payload",
    [
        "not JSON",
        '{"fql":',
        "{}",
        '{"fql":null,"explanation":null}',
        '{"fql":"column_0=4","explanation":"No column"}',
        '{"fql":"","explanation":null}',
        '{"fql":null,"explanation":"  "}',
        '{"fql":4,"explanation":null}',
        '{"fql":"column_0=4","explanation":null,"aliases":[]}',
    ],
)
async def test_invalid_structured_result_makes_one_generation(
    mode: OutputMode,
    payload: str,
) -> None:
    from pydantic_ai.models.function import FunctionModel

    calls = 0

    async def respond(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        del messages
        nonlocal calls
        calls += 1
        return _response(mode, info, payload)

    provider = _provider()
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]), "Keep four"
    )
    with patch.object(
        provider,
        "create_model",
        return_value=FunctionModel(respond, profile=_profile(mode)),
    ):
        with pytest.raises(
            TableFilterOutputError, match="invalid table-filter result"
        ):
            await provider.table_filter_completion(
                prompt,
                None,
                SpanInfo(endpoint="table_filter", model="openai/test"),
            )
    assert calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "FQL",
        "FQL\n",
        "FQL\n \n",
        "column_0=4",
        '{"fql":"column_0=4","explanation":null}',
    ],
)
async def test_invalid_text_result_makes_one_generation(payload: str) -> None:
    from pydantic_ai.models.function import FunctionModel

    calls = 0

    async def respond(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        del messages
        nonlocal calls
        calls += 1
        return _response("text", info, payload)

    provider = _provider()
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]), "Keep four"
    )
    with patch.object(
        provider,
        "create_model",
        return_value=FunctionModel(respond, profile=_profile("text")),
    ):
        with pytest.raises(TableFilterOutputError):
            await provider.table_filter_completion(
                prompt,
                None,
                SpanInfo(endpoint="table_filter", model="openai/test"),
            )
    assert calls == 1


@pytest.mark.parametrize("mode", MODES)
async def test_provider_failure_has_no_transport_fallback(
    mode: OutputMode,
) -> None:
    from pydantic_ai.models.function import FunctionModel

    calls = 0

    async def respond(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        del messages, info
        nonlocal calls
        calls += 1
        raise RuntimeError("Provider unavailable")

    provider = _provider()
    prompt = build_table_filter_prompt(
        FilterContext(row_count=None, columns=[], omissions=[]), "Keep four"
    )
    with patch.object(
        provider,
        "create_model",
        return_value=FunctionModel(respond, profile=_profile(mode)),
    ):
        with pytest.raises(RuntimeError, match="Provider unavailable"):
            await provider.table_filter_completion(
                prompt,
                None,
                SpanInfo(endpoint="table_filter", model="openai/test"),
            )
    assert calls == 1
