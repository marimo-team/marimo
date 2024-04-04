# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Generator, Optional

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import AiCompletionRequest
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


@router.post("/completion")
@requires("edit")
async def ai_completion(
    *,
    request: Request,
) -> StreamingResponse:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="OpenAI not installed"
        ) from None

    app_state = AppState(request)
    app_state.require_current_session()
    config = app_state.config_manager.get_config(hide_secrets=False)
    body = await parse_request(request, cls=AiCompletionRequest)

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
    model: str = (
        config.get("ai", {}).get("open_ai", {}).get("model", "gpt-3.5-turbo")
    )
    if not model:
        model = "gpt-3.5-turbo"

    client = OpenAI(api_key=key, base_url=base_url)

    system_prompt = (
        "You are a helpful assistant that can answer questions "
        "about python code. You can only output python code. "
        "Do not describe the code, just write the code."
        "Do not output markdown or backticks. When using matplotlib "
        "to show plots, use plt.gca() instead of plt.show()."
    )

    prompt = body.prompt
    if body.include_other_code:
        prompt = (
            f"{prompt}\n\nCode from other cells:\n{body.include_other_code}"
        )
    if body.code.strip():
        prompt = f"{prompt}\n\nCurrent code:\n{body.code}"

    response = client.chat.completions.create(
        model=model,
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

    # If it starts or ends with markdown, remove it
    def stream_response() -> Generator[str, None, None]:
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

    return StreamingResponse(
        content=stream_response(),
        media_type="application/json",
    )
