# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)

from marimo import _loggers
from marimo._ai._convert import convert_to_ai_sdk_messages
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
    FIM_MIDDLE_TAG,
    FIM_PREFIX_TAG,
    FIM_SUFFIX_TAG,
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
    from collections.abc import AsyncGenerator

    from starlette.requests import Request


LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


async def safe_stream_wrapper(
    stream_generator: AsyncGenerator[str, None],
    text_only: bool,
) -> AsyncGenerator[str, None]:
    """
    Wraps a streaming generator to catch and handle errors gracefully.

    Args:
        stream_generator: The original streaming generator
        text_only: Whether to return text only or the full AI SDK stream protocol format

    Yields:
        Stream chunks or error messages in AI SDK stream protocol format
    """
    try:
        async for chunk in stream_generator:
            yield chunk
    except Exception as e:
        LOGGER.error("Error in AI streaming response: %s", str(e))
        # Send an error message using AI SDK stream protocol format
        # Error Part format: 3:string\n
        text = str(e)
        if text_only:
            yield convert_to_ai_sdk_messages(text, "error")
        else:
            yield text


def get_ai_config(config: MarimoConfig) -> AiConfig:
    ai_config = config.get("ai", None)
    LOGGER.debug(f"ai_config: {ai_config}")
    if ai_config is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="AI is not configured. Configure them in the settings dialog.",
        )
    return ai_config


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
    response = await provider.stream_completion(
        messages=[ChatMessage(role="user", content=prompt)],
        system_prompt=system_prompt,
        max_tokens=get_max_tokens(config),
    )

    return StreamingResponse(
        content=safe_stream_wrapper(
            without_wrapping_backticks(
                provider.as_stream_response(
                    response, StreamOptions(text_only=True)
                )
            ),
            text_only=True,
        ),
        media_type="application/json",
        headers={"x-vercel-ai-data-stream": "v1"},
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
    response = await provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )

    return StreamingResponse(
        content=safe_stream_wrapper(
            provider.as_stream_response(
                response, StreamOptions(format_stream=True, text_only=False)
            ),
            text_only=False,
        ),
        media_type="application/json",
        headers={"x-vercel-ai-data-stream": "v1"},
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
    # Use FIM (Fill-In-Middle) format for inline completion
    prompt = f"{FIM_PREFIX_TAG}{body.prefix}{FIM_SUFFIX_TAG}{body.suffix}{FIM_MIDDLE_TAG}"
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
    try:
        response = await provider.stream_completion(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=INLINE_COMPLETION_MAX_TOKENS,
        )

        content = await provider.collect_stream(response)
    except Exception as e:
        LOGGER.error("Error in AI inline completion: %s", str(e))
        raise HTTPException(
            status_code=500,  # Internal Server Error
            detail=f"AI completion failed: {str(e)}",
        ) from None

    # Filter out `<|file_separator|>` which is sometimes returned FIM models
    content = content.replace("<|file_separator|>", "")

    return PlainTextResponse(
        content=content,
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

    try:
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
    except Exception as e:
        LOGGER.error("Error invoking AI tool %s: %s", body.tool_name, str(e))
        # Return error response instead of letting it crash
        error_response = InvokeAiToolResponse(
            success=False,
            tool_name=body.tool_name,
            result=None,
            error=f"Tool invocation failed: {str(e)}",
        )
        return JSONResponse(content=asdict(error_response))
