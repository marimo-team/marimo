# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, NoReturn

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)

from marimo import _loggers
from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig, MarimoConfig
from marimo._server.ai.config import (
    AnyProviderConfig,
    get_autocomplete_model,
    get_chat_model,
    get_edit_model,
    get_max_tokens,
)
from marimo._server.ai.prompts import (
    FILL_ME_TAG,
    get_chat_system_prompt,
    get_inline_system_prompt,
    get_refactor_or_insert_notebook_cell_system_prompt,
)
from marimo._server.ai.providers import (
    StreamOptions,
    get_completion_provider,
    without_wrapping_backticks,
)
from marimo._server.ai.tools import get_tool_manager
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import (
    AiCompletionRequest,
    AiInlineCompletionRequest,
    ChatRequest,
)
from marimo._server.models.models import (
    InvokeAiToolRequest,
    InvokeAiToolResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request


LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


def get_ai_config(config: MarimoConfig) -> AiConfig:
    ai_config = config.get("ai", None)
    LOGGER.debug(f"ai_config: {ai_config}")
    if ai_config is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="AI is not configured. Configure them in the settings dialog.",
        )
    return ai_config


def parse_model_format(model: str) -> tuple[str, str]:
    """Parse model format <format>/<model> and return (format, model_name).

    Args:
        model: Model string in format 'format/model' (e.g., 'openai/gpt-4', 'anthropic/claude-3')

    Returns:
        Tuple of (format, model_name)

    Raises:
        HTTPException: If model format is invalid or format is not supported
    """

    def raise_error() -> NoReturn:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid model format '{model}'. Expected format: '<provider>/<model>' (e.g., 'openai/gpt-4', 'anthropic/claude-3', 'google/gemini-pro')",
        )

    if "/" not in model:
        raise_error()

    parts = model.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise_error()

    format_name, model_name = parts

    # Validate supported formats
    supported_formats = {"openai", "anthropic", "google", "bedrock"}
    if format_name not in supported_formats:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unsupported provider '{format_name}'. Supported providers: {', '.join(sorted(supported_formats))}",
        )

    return format_name, model_name


@router.post("/completion")
@requires("edit")
async def ai_completion(
    *,
    request: Request,
) -> StreamingResponse:
    """
    requestBody:
        description: The request body for AI completion
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/AiCompletionRequest"
    responses:
        200:
            description: Get AI completion for a prompt
            content:
                application/json:
                    schema:
                        type: object
                        additionalProperties: true
    """
    app_state = AppState(request)
    app_state.require_current_session()
    config = app_state.app_config_manager.get_config(hide_secrets=False)
    body = await parse_request(
        request, cls=AiCompletionRequest, allow_unknown_keys=True
    )
    ai_config = get_ai_config(config)

    custom_rules = ai_config.get("rules", None)

    system_prompt = get_refactor_or_insert_notebook_cell_system_prompt(
        language=body.language,
        is_insert=False,
        custom_rules=custom_rules,
        cell_code=body.code,
        selected_text=body.selected_text,
        other_cell_codes=body.include_other_code,
        context=body.context,
    )
    prompt = body.prompt

    model = get_edit_model(ai_config)
    provider = get_completion_provider(
        AnyProviderConfig.for_model(model, ai_config),
        model=model,
    )
    response = provider.stream_completion(
        messages=[ChatMessage(role="user", content=prompt)],
        system_prompt=system_prompt,
        max_tokens=get_max_tokens(config),
    )

    return StreamingResponse(
        content=without_wrapping_backticks(
            provider.as_stream_response(
                response, StreamOptions(text_only=True)
            )
        ),
        media_type="application/json",
    )


@router.post("/chat")
@requires("edit")
async def ai_chat(
    *,
    request: Request,
) -> StreamingResponse:
    """
    requestBody:
        description: The request body for AI chat
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ChatRequest"
    """
    app_state = AppState(request)
    app_state.require_current_session()
    config = app_state.app_config_manager.get_config(hide_secrets=False)
    body = await parse_request(
        request, cls=ChatRequest, allow_unknown_keys=True
    )
    ai_config = get_ai_config(config)
    custom_rules = ai_config.get("rules", None)
    messages = body.messages

    # Get the system prompt
    system_prompt = get_chat_system_prompt(
        custom_rules=custom_rules,
        context=body.context,
        include_other_code=body.include_other_code,
        mode=ai_config.get("mode", "manual"),
    )

    max_tokens = get_max_tokens(config)

    model = body.model or get_chat_model(ai_config)
    provider = get_completion_provider(
        AnyProviderConfig.for_model(model, ai_config),
        model=model,
    )
    response = provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )

    return StreamingResponse(
        content=provider.as_stream_response(
            response, StreamOptions(format_stream=True)
        ),
        media_type="application/json",
    )


@router.post("/inline_completion")
@requires("edit")
async def ai_inline_completion(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        description: The request body for AI inline completion
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/AiInlineCompletionRequest"
    responses:
        200:
            description: Get AI inline completion for code
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    app_state.require_current_session()
    config = app_state.app_config_manager.get_config(hide_secrets=False)
    body = await parse_request(
        request, cls=AiInlineCompletionRequest, allow_unknown_keys=True
    )
    prompt = f"{body.prefix}{FILL_ME_TAG}{body.suffix}"
    messages = [ChatMessage(role="user", content=prompt)]
    system_prompt = get_inline_system_prompt(language=body.language)

    # This is currently not configurable and smaller than the default
    # of 4096, since it is smaller/faster for inline completions
    INLINE_COMPLETION_MAX_TOKENS = 1024

    ai_config = get_ai_config(config)

    model = get_autocomplete_model(config)
    provider_config = AnyProviderConfig.for_model(model, ai_config)
    # Inline completion never uses tools
    if provider_config.tools:
        provider_config.tools.clear()

    provider = get_completion_provider(provider_config, model=model)
    response = provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=INLINE_COMPLETION_MAX_TOKENS,
    )

    return PlainTextResponse(
        content=provider.collect_stream(response),
        media_type="text/plain",
    )


@router.post("/invoke_tool")
@requires("edit")
async def invoke_tool(
    *,
    request: Request,
) -> JSONResponse:
    """
    requestBody:
        description: The request body for tool invocation
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/InvokeAiToolRequest"
    responses:
        200:
            description: Tool invocation result
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/InvokeAiToolResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session()

    body = await parse_request(request, cls=InvokeAiToolRequest)

    # Invoke the tool
    result = await get_tool_manager().invoke_tool(
        body.tool_name, body.arguments
    )

    # Create and return the response
    response = InvokeAiToolResponse(
        success=result.error is None,
        tool_name=result.tool_name,
        result=result.result,
        error=result.error,
    )

    return JSONResponse(content=asdict(response))


@router.post("/compat/chat/completions")
@requires("edit")
async def compat_chat_completions(
    *,
    request: Request,
) -> Any:
    """
    OpenAI-compatible chat completions endpoint.

    requestBody:
        description: The request body for chat completions
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ChatCompletionRequest"
    responses:
        200:
            description: Chat completion response
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            choices:
                                type: array
                                items:
                                    type: object
                        additionalProperties: true
    """
    app_state = AppState(request)
    app_state.require_current_session()
    config = app_state.app_config_manager.get_config(hide_secrets=False)
    body = await request.json()
    ai_config = get_ai_config(config)

    full_model = body.pop("model", None)
    if full_model is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Model is required",
        )
    # Parse and validate model format
    format_name, model_name = parse_model_format(full_model)

    # Config for
    scope = request.headers.get("x-marimo-ai-scope", None)
    if scope == "next-edit-prediction":
        provider_config = AnyProviderConfig.for_completion(
            config["completion"],
        )
    else:
        provider_config = AnyProviderConfig.for_model(model_name, ai_config)

    supported_providers = {"openai"}

    if format_name not in supported_providers:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unsupported provider '{format_name}'. Supported providers: {', '.join(sorted(supported_providers))}",
        )

    # Create provider
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url,
    )

    stream = body.pop("stream", False)
    if stream:
        return client.chat.completions.create(
            **stream,
            model=model_name,
            stream=True,
        )
    response = await client.chat.completions.create(
        **body,
        model=model_name,
        stream=False,
    )
    return JSONResponse(content=response.to_dict())
