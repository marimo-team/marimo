# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Optional

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import StreamingResponse

from marimo import _loggers
from marimo._config.config import MarimoConfig
from marimo._server.ai.prompts import Prompter
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import (
    AiCompletionRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from anthropic import (  # type: ignore[import-not-found]
        Client,
        Stream as AnthropicStream,
    )
    from anthropic.types import (  # type: ignore[import-not-found]
        RawMessageStreamEvent,
    )
    from google.generativeai import (  # type: ignore[import-not-found]
        GenerativeModel,
    )
    from google.generativeai.types import (  # type: ignore[import-not-found]
        GenerateContentResponse,
    )
    from openai import (  # type: ignore[import-not-found]
        OpenAI,
        Stream as OpenAiStream,
    )
    from openai.types.chat import (  # type: ignore[import-not-found]
        ChatCompletionChunk,
    )
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


def get_openai_client(config: MarimoConfig) -> "OpenAI":
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="OpenAI not installed. Run `pip install openai`",
        ) from None

    if "ai" not in config:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="OpenAI not configured"
        )
    if "open_ai" not in config["ai"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="OpenAI not configured"
        )
    if "api_key" not in config["ai"]["open_ai"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="OpenAI API key not configured",
        )

    key: str = config["ai"]["open_ai"]["api_key"]
    if not key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="OpenAI API key not configured",
        )
    base_url: Optional[str] = (
        config.get("ai", {}).get("open_ai", {}).get("base_url", None)
    )
    if not base_url:
        base_url = None

    return OpenAI(api_key=key, base_url=base_url)


def get_anthropic_client(config: MarimoConfig) -> "Client":
    try:
        from anthropic import Client  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Anthropic not installed. Run `pip install anthropic`",
        ) from None

    if "ai" not in config:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Anthropic not configured",
        )
    if "anthropic" not in config["ai"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Anthropic not configured",
        )
    if "api_key" not in config["ai"]["anthropic"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Anthropic API key not configured",
        )

    key: str = config["ai"]["anthropic"]["api_key"]

    if not key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Anthropic API key not configured",
        )

    return Client(api_key=key)


def get_model(config: MarimoConfig) -> str:
    model: str = (
        config.get("ai", {}).get("open_ai", {}).get("model", "gpt-4-turbo")
    )
    if not model:
        model = "gpt-4-turbo"
    return model


def get_content(
    response: RawMessageStreamEvent
    | ChatCompletionChunk
    | GenerateContentResponse,
) -> str | None:
    if hasattr(response, "choices"):
        return response.choices[0].delta.content  # type: ignore

    if hasattr(response, "text"):
        return response.text  # type: ignore

    from anthropic.types import (  # type: ignore[import-not-found]
        RawContentBlockDeltaEvent,
        TextDelta,
    )

    if isinstance(response, RawContentBlockDeltaEvent):
        if isinstance(response.delta, TextDelta):
            return response.delta.text  # type: ignore

    return None


def make_stream_response(
    response: OpenAiStream[ChatCompletionChunk]
    | AnthropicStream[RawMessageStreamEvent]
    | GenerateContentResponse,
) -> Generator[str, None, None]:
    original_content = ""
    buffer = ""
    in_code_fence = False

    for chunk in response:
        content = get_content(chunk)
        if not content:
            continue

        buffer += content
        original_content += content
        first_newline = buffer.find("\n")

        # Open code-fence, with no newline
        # wait for the next newline
        if (
            buffer.startswith("```")
            and first_newline == -1
            and not in_code_fence
        ):
            continue

        if (
            buffer.startswith("```")
            and first_newline > 0
            and not in_code_fence
        ):
            # And also ends with ```
            if buffer.endswith("```"):
                yield buffer[first_newline + 1 : -3]
                buffer = ""
                in_code_fence = False
                continue

            yield buffer[first_newline + 1 :]
            buffer = ""
            in_code_fence = True
            continue

        if buffer.endswith("```") and in_code_fence:
            yield buffer[:-3]
            buffer = ""
            in_code_fence = False
            continue

        yield buffer
        buffer = ""

    LOGGER.debug(f"Completion content: {original_content}")


def get_google_client(config: MarimoConfig, model: str) -> "GenerativeModel":
    try:
        import google.generativeai as genai  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                "Google AI not installed. "
                "Run `pip install google-generativeai`"
            ),
        ) from None

    if "ai" not in config or "google" not in config["ai"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Google AI not configured",
        )
    if "api_key" not in config["ai"]["google"]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Google AI API key not configured",
        )

    key: str = config["ai"]["google"]["api_key"]

    if not key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Google AI API key not configured",
        )

    genai.configure(api_key=key)
    return genai.GenerativeModel(
        model_name=model,
        generation_config=genai.GenerationConfig(
            max_output_tokens=1000,
            temperature=0,
        ),
    )


@router.post("/completion")
@requires("edit")
async def ai_completion(
    *,
    request: Request,
) -> StreamingResponse:
    """
    requestBody:
        description: The prompt to get AI completion for
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
    config = app_state.config_manager.get_config(hide_secrets=False)
    body = await parse_request(request, cls=AiCompletionRequest)

    prompter = Prompter(body.code, body.include_other_code, body.context)
    system_prompt = Prompter.get_system_prompt(body.language)
    prompt = prompter.get_prompt(body.prompt)

    model = get_model(config)

    # If the model starts with claude, use anthropic
    if model.startswith("claude"):
        anthropic_client = get_anthropic_client(config)
        anthropic_response = anthropic_client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            system=system_prompt,
            stream=True,
            temperature=0,
        )

        return StreamingResponse(
            content=make_stream_response(anthropic_response),
            media_type="application/json",
        )

    # If the model starts with google/gemini, use Google AI
    if model.startswith("google") or model.startswith("gemini"):
        google_client = get_google_client(config, model)
        google_response = google_client.generate_content(
            contents=prompt,
            stream=True,
        )

        return StreamingResponse(
            content=make_stream_response(google_response),
            media_type="application/json",
        )

    openai_client = get_openai_client(config)
    response = openai_client.chat.completions.create(
        model=get_model(config),
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        stream=True,
    )

    return StreamingResponse(
        content=make_stream_response(response),
        media_type="application/json",
    )
