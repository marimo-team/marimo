# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import (
    PlainTextResponse,
    Response,
    StreamingResponse,
)

from marimo import _loggers
from marimo._ai._convert import convert_to_ai_sdk_messages
from marimo._ai._pydantic_ai_utils import create_simple_prompt
from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig, MarimoConfig
from marimo._server.ai.config import (
    AnyProviderConfig,
    get_autocomplete_model,
    get_chat_model,
    get_edit_model,
    get_max_tokens,
)
from marimo._server.ai.mcp import MCPServerStatus, get_mcp_client
from marimo._server.ai.prompts import (
    FIM_MIDDLE_TAG,
    FIM_PREFIX_TAG,
    FIM_SUFFIX_TAG,
    get_chat_system_prompt,
    get_inline_system_prompt,
    get_refactor_or_insert_notebook_cell_system_prompt,
)
from marimo._server.ai.providers import (
    PydanticProvider,
    StreamOptions,
    get_completion_provider,
    without_wrapping_backticks,
)
from marimo._server.ai.tools.tool_manager import get_tool_manager
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import (
    AiCompletionRequest,
    AiInlineCompletionRequest,
    ChatRequest,
)
from marimo._server.models.models import (
    InvokeAiToolRequest,
    InvokeAiToolResponse,
    MCPRefreshResponse,
    MCPStatusResponse,
)
from marimo._server.responses import StructResponse
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request
    from starlette.responses import ContentStream

# Taken from pydantic_ai.ui import SSE_CONTENT_TYPE
SSE_CONTENT_TYPE = "text/event-stream"


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
        if text_only:
            yield str(e)
        else:
            yield convert_to_ai_sdk_messages(str(e), "error")


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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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
    use_messages = len(body.messages) >= 1  # Deprecated
    use_ui_messages = len(body.ui_messages) >= 1

    system_prompt = get_refactor_or_insert_notebook_cell_system_prompt(
        language=body.language,
        is_insert=False,
        support_multiple_cells=use_messages or use_ui_messages,
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

    if isinstance(provider, PydanticProvider):
        # Currently, only useChat (use_messages=True) supports UI messages
        # So, we can stream back the UI messages here. Else, we stream back the text.
        if use_ui_messages:
            return await provider.stream_completion(
                messages=body.ui_messages,
                system_prompt=system_prompt,
                max_tokens=get_max_tokens(config),
                additional_tools=[],
            )
        response = provider.stream_text(
            user_prompt=prompt,
            messages=body.ui_messages,
            system_prompt=system_prompt,
            max_tokens=get_max_tokens(config),
            additional_tools=[],
        )
        safe_content = safe_stream_wrapper(response, text_only=False)
        content_without_wrapping = without_wrapping_backticks(safe_content)
        return StreamingResponse(
            content=content_without_wrapping,
            media_type="application/json",
            headers={"x-vercel-ai-data-stream": "v1"},
        )

    messages = (
        body.messages
        if use_messages
        else [ChatMessage(role="user", content=prompt)]
    )

    response = await provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=get_max_tokens(config),
        additional_tools=[],
    )

    # Pass back the entire SDK message if the frontend can handle it
    content: ContentStream
    if use_messages:
        content = safe_stream_wrapper(
            provider.as_stream_response(
                response, StreamOptions(format_stream=True, text_only=False)
            ),
            text_only=False,
        )
    else:
        content = safe_stream_wrapper(
            without_wrapping_backticks(
                provider.as_stream_response(
                    response, StreamOptions(text_only=True)
                )
            ),
            text_only=True,
        )

    return StreamingResponse(
        content=content,
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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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
    session_id = app_state.require_current_session_id()
    accept = request.headers.get("accept", SSE_CONTENT_TYPE)
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
        session_id=session_id,
    )

    max_tokens = get_max_tokens(config)

    model = body.model or get_chat_model(ai_config)
    provider = get_completion_provider(
        AnyProviderConfig.for_model(model, ai_config),
        model=model,
    )
    additional_tools = body.tools or []

    stream_options = StreamOptions(
        format_stream=True, text_only=False, accept=accept
    )

    if isinstance(provider, PydanticProvider):
        return await provider.stream_completion(
            messages=body.ui_messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            additional_tools=additional_tools,
            stream_options=stream_options,
        )

    response = await provider.stream_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        additional_tools=additional_tools,
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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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
        if isinstance(provider, PydanticProvider):
            content = await provider.completion(
                messages=[create_simple_prompt(prompt)],
                system_prompt=system_prompt,
                max_tokens=INLINE_COMPLETION_MAX_TOKENS,
                additional_tools=[],
            )
        else:
            response = await provider.stream_completion(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=INLINE_COMPLETION_MAX_TOKENS,
                additional_tools=[],
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
) -> Response:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

        return StructResponse(
            InvokeAiToolResponse(
                success=result.error is None,
                tool_name=result.tool_name,
                result=result.result,
                error=result.error,
            )
        )

    except Exception as e:
        LOGGER.error("Error invoking AI tool %s: %s", body.tool_name, str(e))
        # Return error response instead of letting it crash
        return StructResponse(
            InvokeAiToolResponse(
                success=False,
                tool_name=body.tool_name,
                result=None,
                error=f"Tool invocation failed: {str(e)}",
            )
        )


@router.get("/mcp/status")
@requires("edit")
async def mcp_status(
    *,
    request: Request,
) -> Response:
    """
    responses:
        200:
            description: Get MCP server status
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/MCPStatusResponse"
    """
    del request
    try:
        # Try to get MCP client
        mcp_client = get_mcp_client()

        # Get all server statuses
        server_statuses = mcp_client.get_all_server_statuses()

        # Map internal status enum to API status strings
        status_map: dict[
            MCPServerStatus,
            Literal["pending", "connected", "disconnected", "failed"],
        ] = {
            MCPServerStatus.CONNECTED: "connected",
            MCPServerStatus.CONNECTING: "pending",
            MCPServerStatus.DISCONNECTED: "disconnected",
            MCPServerStatus.ERROR: "failed",
        }

        servers = {
            name: status_map.get(status, "failed")
            for name, status in server_statuses.items()
        }

        # Determine overall status
        overall_status: Literal["ok", "partial", "error"] = "ok"
        if not servers:
            # No servers configured
            overall_status = "ok"
            error = None
        elif all(s == "connected" for s in servers.values()):
            # All servers connected
            overall_status = "ok"
            error = None
        elif any(s == "connected" for s in servers.values()):
            # Some servers connected
            overall_status = "partial"
            failed_servers = [
                name for name, status in servers.items() if status == "failed"
            ]
            error = (
                f"Some servers failed to connect: {', '.join(failed_servers)}"
            )
        else:
            # No servers connected or all failed
            overall_status = "error"
            error = "No MCP servers connected"

        return StructResponse(
            MCPStatusResponse(
                status=overall_status,
                error=error,
                servers=servers,
            )
        )

    except ModuleNotFoundError:
        # MCP dependencies not installed
        return StructResponse(
            MCPStatusResponse(
                status="error",
                error="Missing dependencies. Install with: pip install marimo[mcp]",
                servers={},
            )
        )
    except Exception as e:
        LOGGER.error(f"Error getting MCP status: {e}")
        return StructResponse(
            MCPStatusResponse(
                status="error",
                error=str(e),
                servers={},
            )
        )


@router.post("/mcp/refresh")
@requires("edit")
async def mcp_refresh(
    *,
    request: Request,
) -> Response:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Refresh MCP server configuration
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/MCPRefreshResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session()

    try:
        # Get the MCP client
        mcp_client = get_mcp_client()

        # Get current config
        config = app_state.app_config_manager.get_config(hide_secrets=False)
        mcp_config = config.get("mcp")

        if mcp_config is None:
            return StructResponse(
                MCPRefreshResponse(
                    success=False,
                    error="MCP configuration is not set",
                    servers={},
                )
            )

        # Reconfigure the client with the current configuration
        # This will handle disconnecting/reconnecting as needed
        await mcp_client.configure(mcp_config)

        # Get updated server statuses
        server_statuses = mcp_client.get_all_server_statuses()

        # Map status to success boolean
        servers = {
            name: status == MCPServerStatus.CONNECTED
            for name, status in server_statuses.items()
        }

        # Overall success if all servers are connected (or no servers)
        success = len(servers) == 0 or all(servers.values())

        error = None
        if not success:
            failed_servers = [
                name for name, connected in servers.items() if not connected
            ]
            error = (
                f"Some servers failed to connect: {', '.join(failed_servers)}"
            )

        return StructResponse(
            MCPRefreshResponse(
                success=success,
                error=error,
                servers=servers,
            )
        )

    except ModuleNotFoundError:
        # MCP dependencies not installed
        return StructResponse(
            MCPRefreshResponse(
                success=False,
                error="Missing dependencies. Install with: pip install marimo[mcp]",
                servers={},
            )
        )
    except Exception as e:
        LOGGER.error(f"Error refreshing MCP: {e}")
        return StructResponse(
            MCPRefreshResponse(
                success=False,
                error=str(e),
                servers={},
            )
        )
