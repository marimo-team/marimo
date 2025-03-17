# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse, StreamingResponse

from marimo import _loggers
from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig, MarimoConfig
from marimo._server.ai.prompts import Prompter
from marimo._server.ai.providers import (
    DEFAULT_MODEL,
    get_completion_provider,
    get_max_tokens,
)
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import (
    AiCompletionRequest,
    AiInlineCompletionRequest,
    ChatRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request


LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


def get_ai_config(config: MarimoConfig) -> AiConfig:
    ai_config = config.get("ai", None)
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

    prompter = Prompter(code=body.code)
    system_prompt = Prompter.get_system_prompt(
        language=body.language, custom_rules=custom_rules
    )
    prompt = prompter.get_prompt(
        user_prompt=body.prompt, include_other_code=body.include_other_code
    )

    provider = get_completion_provider(ai_config)
    response = provider.stream_completion(
        messages=[ChatMessage(role="user", content=prompt)],
        system_prompt=system_prompt,
        max_tokens=get_max_tokens(config),
    )

    return StreamingResponse(
        content=provider.as_stream_response(response),
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
    messages = body.messages

    # Get the system prompt
    system_prompt = Prompter.get_chat_system_prompt(
        custom_rules=config.get("ai", {}).get("rules", None),
        variables=body.variables,
        context=body.context,
        include_other_code=body.include_other_code,
    )

    max_tokens = get_max_tokens(config)

    provider = get_completion_provider(ai_config, model_override=body.model)
    response = provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )

    return StreamingResponse(
        content=provider.as_stream_response(response),
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
    prompt = f"{body.prefix}<FILL_ME>{body.suffix}"
    messages = [ChatMessage(role="user", content=prompt)]
    system_prompt = Prompter.get_inline_system_prompt(language=body.language)
    ai_config = get_ai_config(config)

    # This is currently not configurable and smaller than the default
    # of 4096, since it is smaller/faster for inline completions
    INLINE_COMPLETION_MAX_TOKENS = 1024

    try:
        model = config["completion"]["model"] or DEFAULT_MODEL
    except Exception:
        model = DEFAULT_MODEL

    provider = get_completion_provider(ai_config, model_override=model)
    response = provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=INLINE_COMPLETION_MAX_TOKENS,
    )

    return PlainTextResponse(
        content=provider.collect_stream(response),
        media_type="text/plain",
    )
