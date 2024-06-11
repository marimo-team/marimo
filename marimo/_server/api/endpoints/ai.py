# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Optional

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import StreamingResponse

from marimo import _loggers
from marimo._config.config import MarimoConfig
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import (
    AiCompletionRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from openai import OpenAI, Stream  # type: ignore[import-not-found]
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
            status_code=HTTPStatus.BAD_REQUEST, detail="OpenAI not installed"
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


def get_model(config: MarimoConfig) -> str:
    model: str = (
        config.get("ai", {}).get("open_ai", {}).get("model", "gpt-3.5-turbo")
    )
    if not model:
        model = "gpt-3.5-turbo"
    return model


def make_stream_response(
    response: Stream[ChatCompletionChunk],
) -> Generator[str, None, None]:
    # If it starts or ends with markdown, remove it
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            if content.startswith("```python"):
                yield content[9:]
            if content.startswith("```"):
                yield content[4:]
            elif content.endswith("```"):
                yield content[:-3]
            else:
                yield content or ""


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
    client = get_openai_client(config)

    system_prompt = (
        "You are a helpful assistant that can answer questions "
        "about python code. You can only output python code. "
        "1. Do not describe the code, just write the code."
        "2. Do not output markdown or backticks."
        "3. When using matplotlib to show plots,"
        "use plt.gca() instead of plt.show()."
        "4. If an import already exists, do not import it again."
        "5. If a variable is already defined, use another name, or"
        "make it private by adding an underscore at the beginning."
    )

    prompt = body.prompt
    if body.include_other_code:
        prompt = (
            f"{prompt}\n\nCode from other cells:\n{body.include_other_code}"
        )
    if body.code.strip():
        prompt = f"{prompt}\n\nCurrent code:\n{body.code}"

    response = client.chat.completions.create(
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
