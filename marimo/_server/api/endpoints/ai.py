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
from marimo._utils.assert_never import assert_never

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
        config.get("ai", {}).get("open_ai", {}).get("model", "gpt-4-turbo")
    )
    if not model:
        model = "gpt-4-turbo"
    return model


def make_stream_response(
    response: Stream[ChatCompletionChunk],
) -> Generator[str, None, None]:
    original_content = ""
    buffer: str = ""
    in_code_fence = False
    # If it starts or ends with markdown, remove it
    for chunk in response:
        content = chunk.choices[0].delta.content
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

    if body.language == "python":
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
    elif body.language == "markdown":
        system_prompt = (
            "You are a helpful assistant that can answer questions "
            "about markdown. You can only output markdown."
        )
    elif body.language == "sql":
        system_prompt = (
            "You are a helpful assistant that can answer questions "
            "about sql. You can only output sql."
        )
    else:
        assert_never(body.language)

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
